from datetime import datetime
from pathlib import Path
class Logger():
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

    def __init__(self, log_level='DEBUG', name:str=None, file=None):
        if name is not None:
            self.name = name
        else:
            self.name = "logger"
        self.level = self.Levels.index(log_level)

        self.file = None
        if file is not None:
            self.add_logfile(file)

    def add_logfile(self, file):
        if self.file is not None:
            self.file_handle.close()

        self.file = Path(file)
        self.file.parent.mkdir(exist_ok=True)
        self.file_handle = self.file.open("w")

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

    def log(self, *msg, echo=False, log_time=True):
        if log_time:
            now = datetime.now()
            text = now.strftime("%y/%m/%d %H:%M:%S, ") + f"{now.timestamp():.3f}, "
        else:
            text = ""

        for item in msg:
            text += str(item)
            text += ", "

        if echo:
            print(text)

        self.file_handle.write(text + "\n")

    def setLevel(self, log_level):
        assert log_level in self.Levels
        self.level = self.Levels.index(log_level)

    def __del__(self):
        if self.file is not None:
            self.file_handle.close()

class Filter:
    """数据滤波"""
    def __init__(self, data=None, alpha=0.2):
        self._data = data
        self._alpha = alpha

    def update(self, new_data):
        if self._data is None:
            self._data = new_data
        self._data = (1 - self._alpha) * self._data + self._alpha * new_data

    @property
    def data(self):
        if self._data is None:
            return 0
        return self._data

    @data.setter
    def data(self, new_data):
        if self._data is None or self._alpha == 1:
            self._data = new_data
        self._data = (1 - self._alpha) * self._data + self._alpha * new_data


if __name__ == '__main__':
    lg = Logger(file='./log.txt')
    lg.log("tests.")
    lg.log("data.", "ad", 12)
