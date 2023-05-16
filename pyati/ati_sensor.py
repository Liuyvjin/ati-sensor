import socket
import struct
from threading import Thread, Lock, Event
from time import sleep
from datetime import datetime
import numpy as np


class Logger():
    name = "logger"

    grey = "\x1b[38;20m"
    green="\x1b[32m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    Levels = ["DEBUG", "INFO", "WARNING", "ERROR", "FATAL"]
    level = 1

    ColorMap = {
        "DEBUG" : grey,
        "INFO": green,
        "WARNING": yellow,
        "ERROR": red ,
        "FATAL": bold_red
    }

    def __init__(self, log_level='DEBUG', name:str=None):
        if name is not None:
            self.name = name
        self.level = self.Levels.index(log_level)

    def color_print(self, levelname, *msg):
        now = datetime.now().strftime('%H:%M:%S')
        prefix = self.ColorMap.get(levelname) + f"[{levelname:>5}] " +\
            self.reset + now + f" [{self.name}]:"
        print(prefix, *msg)

    def debug(self, *msg):
        if self.level < 1:
            self.color_print("DEBUG", *msg)

    def info(self, *msg):
        if self.level < 2:
            self.color_print("INFO", *msg)

    def warning(self, *msg):
        if self.level < 3:
            self.color_print("WARNING", *msg)

    def error(self, *msg):
        if self.level < 4:
            self.color_print("ERROR", *msg)

    def fatal(self, *msg):
        if self.level < 5:
            self.color_print("FATAL", *msg)

    def setLevel(self, log_level):
        assert log_level in self.Levels
        self.level = self.Levels.index(log_level)


class RDTCommand():
    HEADER = 0x1234
    # Possible values for command
    CMD_STOP_STREAMING = 0
    CMD_START_STREAMING = 2
    # Special values for sample count
    INFINITE_SAMPLES = 0

    @classmethod
    def pack(self, command, count=INFINITE_SAMPLES):
        return struct.pack('!HHI', self.HEADER, command, count)


class ATISensor:
    '''The class interface for an ATI Force/Torque sensor.'''
    counts_per_force = 1000000
    scale = 1.0 / counts_per_force

    def __init__(self, ip="192.168.1.1"):
        self.ip = ip
        self.port = 49152
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.streaming = False
        self._mutex = Lock()
        self._connected = Event()
        self.count = 0
        self.logger = Logger(log_level="DEBUG", name="ATI")
        self.mean = np.zeros((6,), np.float64)
        self._data = self.mean
        self.connect()

    @property
    def connected(self):
        return self._connected.is_set()

    @property
    def data(self):
        """current data"""
        if self.streaming:
            self._mutex.acquire()
            tmp_data = self._data
            self._mutex.release()
        else:
            tmp_data = self.get_n_samples(1)[0]
        return tmp_data - self.mean

    def connect(self):
        retry = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(1)
        self.sock.settimeout(10)
        while retry < 5: # 循环条件为未连接且未达到最大重试次数
            try:
                self.sock.connect((self.ip, self.port))
                self.logger.info("socket is connected!")
                self._connected.set()
                return
            except socket.timeout: # 如果连接超时，捕获异常
                retry += 1
                self.logger.warning("socket connection timeout, retrying...")
            except Exception as e:
                retry += 1
                self.logger.warning("socket connection failed, error:", e)
            sleep(1)

        self.logger.error("socket connection failed after 5 attempts")
        raise

    def send_cmd(self, command, count=0):
        if self._connected.wait(1):
            self.sock.send(RDTCommand.pack(command, count))
        else:
            raise

    def recv_data(self):
        if self._connected.wait(1):
            rawdata = self.sock.recv(1024)
            raw_data = struct.unpack('!3I6i', rawdata)[3:]
            self.count += 1
            return np.array(raw_data) * self.scale
        else:
            raise

    def get_n_samples(self, n=1):
        """读取 n 个 sample"""
        n = max(1, int(n))
        samples = np.empty((n, 6))
        self.send_cmd(RDTCommand.CMD_START_STREAMING, n)
        for i in range(n):
            samples[i] = self.recv_data()
        return samples

    def tare(self, n=10):
        """传感器去皮
            n (int, optional): 取平均的样本数
        """
        samples = self.get_n_samples(n)
        self.mean = samples.mean(axis=0, keepdims=False)

    def zero(self):
        '''Remove the mean found with `tare` to start receiving raw sensor values.'''
        self.mean = np.zeros((6,))

    def start_stream(self):
        """开始持续高速传输数据"""
        self._data = self.get_n_samples(1)[0] - self.mean
        self.send_cmd(RDTCommand.CMD_START_STREAMING, RDTCommand.INFINITE_SAMPLES)
        self.streaming = True
        self.thread = Thread(target=self.recv_thread, daemon=True)
        self.thread.start()
        self.logger.info("Start streaming")
        sleep(0.1)

    def stop_stream(self):
        """开始持续高速传输数据"""
        self.send_cmd(RDTCommand.CMD_STOP_STREAMING, 0)
        self.streaming = False
        self.logger.info("Stop streaming")

    def recv_thread(self):
        while self.streaming:
            tmp_data = self.recv_data()
            self._mutex.acquire()
            self._data = tmp_data
            self._mutex.release()


if __name__ == '__main__':
    np.set_printoptions(formatter={'float': lambda x: "{0:0.3f}".format(x)})

    ati = ATISensor("192.168.1.1")
    ati.tare()
    while True:
        print(ati.data)
        sleep(0.1)
