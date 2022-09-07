import asyncio
import uuid
import time
import random
import sys
import ssl
import os

server_host = "localhost"
server_port = 15151

worker_count = 5

tranid = uuid.uuid4()

socket_min_lifetime = 60
socket_min_speed = 2000000

delayed_start_prob = 0.5
delayed_start_min = 5
delayed_start_max = 30

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

class DesWorker:
    def __init__(self, workq: asyncio.Queue):
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self.started_at: float = 0
        self.last_send_time: float = 0
        self.last_chunk_size: int = 0
        self.workq = workq

    async def setup_socket(self):
        """Low level method to set up a working socket"""
        while self.reader is None or self.writer is None:
            try:
                self.started_at = time.time()
                self.reader, self.writer = await get_socket()
            except Exception:
                log("Error setting up socket. Retrying")

    def reborn_check(self, chunk: bytes, offset: int):
        """Check if the socket needs to be reborn"""
        this_send_time = time.time()
        speed = self.last_chunk_size / (this_send_time - self.last_send_time)
        log(f"Speed: {speed:0f}")
        self.last_send_time = this_send_time
        self.last_chunk_size = len(chunk)
        if (time.time() - self.started_at) < socket_min_lifetime:
            # Too young
            return False
        if speed > socket_min_speed:
            # Fast enough
            return False
        # Reborn by default
        return True
        
    async def go(self, chunk: bytes, offset: int):
        while True:
            if self.writer is None:
                log("Setting up socket")
                await self.setup_socket()
            # self.writer must not be none here
            self.writer.write(tranid.bytes)
            self.writer.write(offset.to_bytes(8, 'big'))
            self.writer.write(len(chunk).to_bytes(8, 'big'))
            self.writer.write(chunk)
            log(f"Sending chunk offset {offset}")
            try:
                await self.writer.drain()

                resp = await self.reader.readline()
                if len(resp) == 0:
                    raise RuntimeError("EOF received")
                break
            except Exception:
                # Failed
                log(f"Failed writing chunk offset {offset}")
                await self.teardown_socket()
                continue
        if self.reborn_check(chunk, offset):
            log(f"Tear down socket")
            await self.teardown_socket()
            await self.setup_socket()
        log(f"Finished sending chunk offset {offset}")
            
    async def teardown_socket(self):
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
        self.writer = None
        self.reader = None

    async def setup(self):
        await self.setup_socket()

    async def loop(self):
        if random.random() < delayed_start_prob:
            delay = delayed_start_min + random.random() * (delayed_start_max - delayed_start_min)
            log("Delaying worker start for {:.0f}s".format(delay))
            await asyncio.sleep(delay)
        log("Worker loop started")
        if self.writer is None:
            await self.setup_socket()
        keep_working = True
        while keep_working:
            piece = await self.workq.get()
            if 'finish' in piece:
                keep_working = False
                continue
            chunk = piece['chunk']
            offset = piece['offset']
            log(f"Going chunk length {len(chunk)} offset {offset}")
            await self.go(chunk, offset)
        # Done
        log("Worker loop end")
        # Send finish to other side
        
        self.writer.write(tranid.bytes)
        self.writer.write(b'\xff\xff\xff\xff\xff\xff\xff\xff')
        self.writer.write(b'\xff\xff\xff\xff\xff\xff\xff\xff')
        await self.writer.drain()
        
        await self.teardown_socket()
        
class Des:
    def __init__(self):
        self.piece_size = 1048576
        self.worker_count = worker_count
        self.workq = asyncio.Queue(2) # Minimum 1 make it small
        self.workers = [DesWorker(self.workq) for _i in range(self.worker_count)]
        self.worker_tasks = [None] * self.worker_count
        self.next_piece = b''
        self.next_offset = 0
        self.finish = asyncio.Event()
    
    async def go(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Run Des in a socket server callback"""
        for w in self.workers:
            await w.setup()
        self.worker_tasks = [asyncio.create_task(w.loop()) for w in self.workers]

        keep_working = True
        while keep_working:
            resp = await reader.read(self.piece_size)
            if len(resp) == 0:
                log("EOF reached")
                if len(self.next_piece) > 0:
                    # Push last to work queue
                    await self.workq.put({'chunk': self.next_piece, 'offset': self.next_offset})
                keep_working = False
                continue
            self.next_piece += resp
            if len(self.next_piece) >= self.piece_size:
                # Push it to work queue
                await self.workq.put({'chunk': self.next_piece, 'offset': self.next_offset})
                self.next_offset += len(self.next_piece)
                self.next_piece = b''
        # Finish work
        for w in self.workers:
            await self.workq.put({'finish': 1})
        log("Waiting for workers to end")
        await asyncio.wait(self.worker_tasks)
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        log("des.go finish")
        self.finish.set()

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
    async with server:
        server_task = asyncio.create_task(server.serve_forever())
        try:
            await des.finish.wait()
            server_task.cancel()
        finally:
            log("Removing FIFO")
            os.remove(fifo_fn)
    # Global finish
    reader, writer = await get_socket()
    writer.write(b'\xff\xff\xff\xff\xff\xff\xff\xff') # Bad uuid
    writer.write(b'\xff\xff\xff\xff\xff\xff\xff\xff')
    writer.write(b'\xff\xff\xff\xff\xff\xff\xff\xff') # Bad offset
    writer.write(b'\xff\xff\xff\xff\xff\xff\xff\xff') # Bad length
    await writer.drain()
    writer.close()
    await writer.wait_closed()

if __name__ == "__main__":
    asyncio.run(demo_main())
