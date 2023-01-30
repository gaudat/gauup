import asyncio
import uuid
import time
import random
import sys
import ssl
import os
import socket

tranid = uuid.uuid4()

listen_port = int(sys.argv[1])

worker_count = int(sys.argv[2])

socket_min_lifetime = 60
socket_min_speed = 2000000

def log(*args):
    return print(*args, file=sys.stderr)

class Des:
    def __init__(self):
        self.piece_size = 1048576
        self.worker_count = worker_count # Maximum concurrent connections
        self.workq = asyncio.Queue(2)
        self.works = [None] * self.worker_count
        self.work_status = [None] * self.worker_count # None = no work, <asyncio.Lock> = unlocked: available, locked: working. When task dies the lock is released
        self.next_piece = b''
        self.next_offset = 0
        self.finished = asyncio.Event()
        self.des_finished = asyncio.Event()
        self.conn_count = 0

    async def wait_until_finish(self):
        """Block until Des finish cleaning up"""
        await self.des_finished.wait()
    
    async def send_finish(self, reader, writer):
        log("Sending finish")
        writer.write(b'\xff\xff\xff\xff\xff\xff\xff\xff') # Bad uuid
        writer.write(b'\xff\xff\xff\xff\xff\xff\xff\xff')
        writer.write(b'\xff\xff\xff\xff\xff\xff\xff\xff') # Bad offset
        writer.write(b'\xff\xff\xff\xff\xff\xff\xff\xff') # Bad length
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def do_one_work(self, reader, writer, work_i):
        work = self.works[work_i]
        chunk = work['chunk']
        offset = work['offset']

        writer.write(tranid.bytes)
        writer.write(offset.to_bytes(8, 'big'))
        writer.write(len(chunk).to_bytes(8, 'big'))
        writer.write(chunk)
        log(f"Sending chunk length {len(chunk)} offset {offset}")
        try:
            await writer.drain()
            resp = await reader.readline()
            if len(resp) == 0:
                raise RuntimeError("EOF received")
            log(f"Finished sending chunk offset {offset}")
            return True
        except Exception:
            # Failed
            log(f"Failed writing chunk offset {offset}")
            # Release the lock and let another connection work it
            return False

    async def connect_cb(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Send works when a client connect"""
        self.conn_count += 1
        reborn_state = {
            "started_at": time.time(),
            "last_send_time": 0,
            "last_chunk_size": 0
        } # Local to each worker
        while True:
            # Check if there are any outstanding work
            work_i = None
            while work_i is None:
                for i in range(self.worker_count):
                    if self.work_status[i] is not None:
                        wlock = self.work_status[i]
                        if not wlock.locked():
                            work_i = i
                            async with wlock:
                                work_res = await self.do_one_work(reader, writer, work_i)
                                reborn = self.reborn_check(reborn_state, work_i) # Need work to be vlid
                                if work_res:
                                    # Work is done
                                    self.works[work_i] = None
                                    self.work_status[work_i] = None # Delete while locked
                                    work_i = None
                                if reborn:
                                    log(f"Tear down socket")
                                    writer.close()
                                    await writer.wait_closed()
                                    self.conn_count -= 1
                                    return
                if self.finished.is_set():
                    # Send finish instead
                    log("Sending finish to client")
                    try:
                        await self.send_finish(reader, writer)
                    except Exception:
                        pass
                    writer.close()
                    await writer.wait_closed()
                    self.conn_count -= 1
                    return
                # No work available
                await asyncio.sleep(1)
            
    def reborn_check(self, state, work_i):
        """Check if the socket needs to be reborn"""
        work = self.works[work_i]
        chunk = work['chunk']
        this_send_time = time.time()
        speed = state['last_chunk_size'] / (this_send_time - state['last_send_time'])
        log(f"Speed: {speed:0f}")
        state['last_send_time'] = this_send_time
        state['last_chunk_size'] = len(chunk)
        if (time.time() - state['started_at']) < socket_min_lifetime:
            # Too young
            return False
        if speed > socket_min_speed:
            # Fast enough
            return False
        # Reborn by default
        return True

    async def fill_works_fun(self):
        log("fill_works_fun enter")
        while not self.finished.is_set() or not self.workq.empty():
            while None not in self.work_status:
                await asyncio.sleep(0.1)
            empty_slot = self.work_status.index(None)
            assert self.works[empty_slot] is None
            workitem = await self.workq.get()
            log(f"fill_works_fun get len {len(workitem['chunk'])} offset {workitem['offset']}")
            self.works[empty_slot] = workitem
            self.work_status[empty_slot] = asyncio.Lock()
        log("fill_works_fun exit")

    async def go(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Run Des in a socket server callback"""
        log("des.go called")
        self.fill_works_task = asyncio.create_task(self.fill_works_fun()) # Maintain reference so job is not GC'd
        keep_working = True
        while keep_working:
            resp = await reader.read(self.piece_size) # Blocks until ctrl+c on nc
            if len(resp) == 0:
                log("EOF reached")
                if len(self.next_piece) > 0:
                    # Push last to work queue
                    log(f"Submit last len {len(self.next_piece)} offset {self.next_offset}")
                    await self.workq.put({'chunk': self.next_piece, 'offset': self.next_offset})
                keep_working = False
                continue
            self.next_piece += resp
            if len(self.next_piece) >= self.piece_size:
                # Push it to work queue
                log(f"Submit len {len(self.next_piece)} offset {self.next_offset}")
                await self.workq.put({'chunk': self.next_piece, 'offset': self.next_offset})
                self.next_offset += len(self.next_piece)
                self.next_piece = b''
        # Finish work
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        log("Set internal finished flag")
        self.finished.set()
        # Wait for all works to finish
        while self.conn_count > 0:
            log(f"Waiting for {self.conn_count} connections to end")
            await asyncio.sleep(1)
        log("Set external finished flag")
        self.des_finished.set()

class TestDesDataGen:
    def __init__(self):
        self.chunk_size = 32768
        self.total_size = 1000000000
        self.seed = 1234
        self.rng = random.Random(self.seed)
        self.offset = 0

    async def read(self, max_size: int):
        if self.offset >= self.total_size:
            return b''
        if self.offset + self.chunk_size >= self.total_size:
            max_size = self.total_size - self.offset
        chunk = self.rng.choices(range(256), k=max_size)
        self.offset += max_size
        return bytes(chunk)

async def demo_main():
    log("Tran ID:")
    log(tranid.hex)
    fifo_fn = "/tmp/plmbr_{}".format(tranid.hex[:8])
    log("FIFO name:")
    log(fifo_fn)
    des = Des()

    server: asyncio.Server = await asyncio.start_unix_server(des.go, fifo_fn)
    
    sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    sctx.load_cert_chain(
        "/etc/ssl/certs/ssl-cert-snakeoil.pem",
        "/etc/ssl/private/ssl-cert-snakeoil.key"
        )
    tls_server = await asyncio.start_server(
        des.connect_cb,
        host="0.0.0.0", port=listen_port,
        family=socket.AF_INET, flags=socket.SOCK_STREAM,
        ssl=sctx)

    async with server, tls_server:
        server_task = asyncio.create_task(server.serve_forever())
        addrs = ', '.join(str(sock.getsockname()) for sock in tls_server.sockets)
        log(f'Serving on {addrs}')
        tls_server_task = asyncio.create_task(tls_server.serve_forever()) # Reference
        try:
            await des.wait_until_finish()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
            tls_server_task.cancel()
            try:
                await tls_server_task
            except asyncio.CancelledError:
                pass
        finally:
            log("Removing FIFO")
            os.remove(fifo_fn)

if __name__ == "__main__":
    asyncio.run(demo_main())
