import asyncio
import sys
import random
import socket
import ssl

listen_port = 15151

def log(*args):
    return print(*args, file=sys.stderr)

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

    async def go(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Run Ser in a socket server callback"""
        while True:
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
                log("Wrong tranid received")
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

    sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    sctx.load_cert_chain(
        "/etc/ssl/certs/ssl-cert-snakeoil.pem",
        "/etc/ssl/private/ssl-cert-snakeoil.key"
        )
    server = await asyncio.start_server(
        ser.go,
        host="0.0.0.0", port=listen_port,
        family=socket.AF_INET, flags=socket.SOCK_STREAM,
        ssl=sctx)
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    log(f'Serving on {addrs}')

    async with server:
        server_task = asyncio.create_task(server.serve_forever())
        await ser.wait_until_finish()
        log(f'Finished')
        server_task.cancel()

    while not ser.unloadq.empty():
        await ser.unload_q_fun()

if __name__ == "__main__":
    asyncio.run(demo_main())
