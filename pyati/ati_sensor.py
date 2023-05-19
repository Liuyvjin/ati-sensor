import socket
import struct
from threading import Thread, Lock, Event
from time import sleep
import numpy as np

from pyati.general_utils import Filter, Logger
np.set_printoptions(formatter={'float': lambda x: "{0:0.5f},".format(x)})

class RDTCommand():
    HEADER = 0x1234
    # Possible values for command
    CMD_STOP_STREAMING = 0
    CMD_START_STREAMING = 2
    CMD_SET_SOFTWARE_BIAS = 0x0042
    # Special values for sample count
    INFINITE_SAMPLES = 0

    @classmethod
    def pack(self, command, count=INFINITE_SAMPLES):
        return struct.pack('!HHI', self.HEADER, command, count)


class ATISensor:
    '''The class interface for an ATI Force/Torque sensor.'''
    counts_per_force = 1000000
    counts_per_torque = 1000
    scale = 1 / np.array([counts_per_force, counts_per_force, counts_per_force,
                      counts_per_torque, counts_per_torque, counts_per_torque])

    def __init__(self, ip="192.168.1.10",
                 filter_on=False,
                 log_file=None):
        self.ip = ip
        self.port = 49152
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.streaming = False
        self.filter_on = filter_on

        self._mutex = Lock()
        self._connected = Event()

        self.logger = Logger(log_level="DEBUG", name="ATI")

        self.mean = np.zeros((6,), np.float64)

        if filter_on:
            self._data = Filter(np.array(self.mean), 0.3)
        else:
            self._data = Filter(np.array(self.mean), 1)

        self.log_file = log_file if log_file is not None else './data.csv'
        self._log_init = False

        self.connect()

    @property
    def connected(self):
        return self._connected.is_set()

    @property
    def data(self):
        """current data"""
        if self.streaming:
            self._mutex.acquire()
            tmp_data = self._data.data
            self._mutex.release()
        else:
            self._data.update(self.get_n_samples(1)[0])
            tmp_data = self._data.data

        curr_data = tmp_data - self.mean

        return curr_data

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
            raw_data = np.array(struct.unpack('!3I6i', rawdata)[3:])
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

    def get_n_samples_mean(self, n=1):
        """读取 n 个 sample, 并取平均"""
        n = max(1, int(n))
        samples = np.empty((n, 6))
        self.send_cmd(RDTCommand.CMD_START_STREAMING, n)
        for i in range(n):
            samples[i] = self.recv_data()
        return samples.mean(axis=0, keepdims=False)

    def tare(self, n=10):
        """传感器去皮
            n (int, optional): 取平均的样本数
        """
        self.mean = self.get_n_samples_mean(n)

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
            self._data.data = tmp_data
            self._mutex.release()

    def log_data(self, *msg, echo=True):
        if not self._log_init:
            self.logger.add_logfile(self.log_file)
            self.logger.log("Force Units: N, Torque Units: Nmm, Counts per Unit Force: 1000000.0, Counts per Unit Torque: 1000", log_time=False)
            self.logger.log("Time, TimeStamp, Fx, Fy, Fz, Tx, Ty, Tz", log_time=False)
            self._log_init = True

        tmp_data = self.data
        self.logger.log(str(tmp_data)[1:-2], *msg, echo=echo, log_time=True)
        return tmp_data

    def set_bias(self):
        """Set software bias"""
        self.send_cmd(RDTCommand.CMD_SET_SOFTWARE_BIAS, 0)


if __name__ == '__main__':

    ati = ATISensor("192.168.1.1")
    ati.tare()
    while True:
        ati.log_data()
        sleep(0.1)
