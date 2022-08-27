import asyncio
import sys
import random
import socket
import ssl

worker_count = 5
server_host = "localhost"
server_port = 5152

def log(*args):
    return print(*args, file=sys.stderr)

async def get_socket():
    sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    sctx.check_hostname = False
    sctx.verify_mode = ssl.CERT_NONE
    sctx.verify_flags = ssl.VERIFY_DEFAULT
    reader, writer = await asyncio.open_connection(
        server_host, server_port,
        ssl=sctx
    )
    return reader, writer

class Ser:
    def __init__(self):
        self.tranid = None
        self.keep_working = True
        self.unload_q_task = None
        self.out_offset = 0
        self.unloadq = asyncio.PriorityQueue() # (number, data) queue size limited by rx window down
        self.writer = sys.stdout.buffer
        self.finish = asyncio.Event()

    async def wait_until_finish(self):
        await self.finish.wait()

    async def unload_q_fun(self):
        offset, chunk = await self.unloadq.get()
        if offset != self.out_offset:
            log(f"Earliest chunk {offset} expected {self.out_offset}")
            # Put back into q
            # Nothing is run between the get and here so unloadq is guaranteed to be space
            await self.unloadq.put((offset, chunk))
            return
        else:
            log(f"Outputting chunk length {len(chunk)} offset {self.out_offset}")
            self.out_offset += len(chunk)
            self.writer.write(chunk)
            self.writer.flush()

    async def worker(self):
        reader: asyncio.StreamReader = None
        writer: asyncio.StreamWriter = None
        while not self.finish.is_set():
            while (not self.finish.is_set()) and (reader is None or writer is None):
                try:
                    reader, writer = await get_socket()
                except Exception:
                    continue
            await self.go(reader, writer)
            # Clean up socket
            reader = writer = None
        log("Finishing worker")
        if writer is not None:
            writer.close()
            await writer.wait_closed()
            return

    async def go(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Run Ser in a socket server callback"""
        while not self.finish.is_set():
            try:
                tranid = await reader.readexactly(16)
                offset = await reader.readexactly(8)
                clen = await reader.readexactly(8)
            except Exception:
                log("Socket broken when reading header")
                writer.close()
                await writer.wait_closed()
                return
            
            offset = int.from_bytes(offset, 'big')
            clen = int.from_bytes(clen, 'big')
            if self.tranid is None:
                log(f"tranid: {tranid}")
                if offset > 0:
                    log("Ignoring tran since offset is not 0")
                    writer.close()
                    await writer.wait_closed()
                    return
                self.tranid = tranid
            
            if tranid != self.tranid:
                log("Wrong tranid received") # Used as global finish signal
                self.finish.set()
                writer.close()
                await writer.wait_closed()
                return


            if offset == 18446744073709551615 and clen == 18446744073709551615:
                # Finish
                log("Received finish")
                writer.close()
                await writer.wait_closed()
                return


            log(f"Receiving chunk length {clen} offset {offset}")

            chunk = await reader.readexactly(clen)

            # Limit out offset
            while offset > self.out_offset + 50000000:
                log("Cleaning backlog")
                await self.unload_q_fun() # Clean up backlog
                await asyncio.sleep(1)

            await self.unloadq.put((offset, chunk))
            await self.unload_q_fun()

            writer.write(b'OK\n')
            await writer.drain()


class TestSerGlobalWriter:
    def __init__(self):
        self.offset = 0
        self.seed = 1234
        self.rng = random.Random(self.seed)

    def write(self, data):
        assert type(data) == bytes
        refdata = self.rng.choices(range(256), k=len(data))
        refdata = bytes(refdata)
        assert data == refdata

    def flush(self):
        pass

global_writer = TestSerGlobalWriter()

async def demo_main():    
    ser = Ser()

    workers = [asyncio.create_task(ser.worker()) for i in range(worker_count)]

    await asyncio.gather(*workers)

    while not ser.unloadq.empty():
        await ser.unload_q_fun()

if __name__ == "__main__":
    asyncio.run(demo_main())
