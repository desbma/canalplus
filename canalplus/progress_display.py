import abc
import itertools
import shutil
import time


class Progress(metaclass=abc.ABCMeta):

  """ Progress abstract interface. """

  def __init__(self, *, max_updates_per_sec=10):
    self._current_progress = 0
    self._additionnal_info = None
    self._max_updates_per_sec = max_updates_per_sec
    self._last_update_time = 0

  def updateProgress(self, progress):
    """ Change progress percentage value. """
    if (progress < 0) or (progress > 100):
      raise ValueError()
    self._current_progress = progress

  def setAdditionnalInfo(self, info):
    """ Add additionnal text to be displayed with the progress. """
    self._additionnal_info = info

  def display(self):
    """ Display the progress if needed. """
    # short circuit if displaying too fast
    now = time.monotonic()
    if ((self._current_progress != 100) and
            (self._max_updates_per_sec > 0) and
            ((now - self._last_update_time) <= (1 / self._max_updates_per_sec))):
      return
    self._display()
    self._last_update_time = now

  @abc.abstractmethod
  def end(self):
    """ End display. """
    pass

  @abc.abstractmethod
  def _display(self):
    """ Display the progress. """
    pass


class ProgressBar(Progress):

  """ Terminal progress bar. """

  def __init__(self, *, max_updates_per_sec=10, append_eta=False):
    super().__init__(max_updates_per_sec=max_updates_per_sec)
    self._line_with = shutil.get_terminal_size(fallback=(80, 0))[0] - 1
    self._append_eta = append_eta
    self._start_time = None

  def updateProgress(self, progress):
    if self._append_eta and (self._start_time is None):
      self._start_time = time.monotonic()
    super().updateProgress(progress)

  def _display(self):
    """ See Progress._display. """
    bar_width = self._line_with - 8
    if self._append_eta:
      now = time.monotonic()
      eta_s = (100 - self._current_progress) * (now - self._start_time) / max(0.01, self._current_progress)
      if eta_s > (60 * 99):
        h = eta_s // (60 * 60)
        m = (eta_s - h * 60 * 60) // 60
        s = eta_s % 60
        eta_str = "ETA %02u:%02u:%02u" % (h, m, s)
      else:
        m = eta_s // 60
        s = eta_s % 60
        eta_str = "ETA %02u:%02u" % (m, s)
      bar_width -= len(eta_str) + 1
    if self._additionnal_info is not None:
      bar_width -= 1 + len(self._additionnal_info)
      additionnal_info = "%s " % (self._additionnal_info)
    else:
      additionnal_info = ""
    char_progress = int(self._current_progress * bar_width / 100)
    if char_progress == 0:
      bar_str = " " * bar_width
    elif char_progress == bar_width:
      bar_str = "=" * bar_width
    else:
      bar_str = ("%s>" % ("=" * (char_progress - 1))).ljust(bar_width)
    line = "\r%s[%3u%%] [%s]" % (additionnal_info, self._current_progress, bar_str)
    if self._append_eta:
      line = " ".join((line, eta_str))
    print(line, end="")

  def end(self):
    """ See Progress.end. """
    print()


class SimpleProgress(Progress):

  """ Progress percentage display. """

  def __init__(self, *, max_updates_per_sec=10):
    super().__init__(max_updates_per_sec=max_updates_per_sec)

  def _display(self):
    """ See Progress._display. """
    line = "\r%u%%" % (self._current_progress)
    print(line, end="")
    if self._additionnal_info is not None:
      print(" %s" % (self._additionnal_info), end="")

  def end(self):
    """ See Progress.end. """
    print()


class ZenityProgress(SimpleProgress):

  """ Progress producing output to pipe to zenity --progress. """

  def __init__(self, *, max_updates_per_sec=10):
    super().__init__(max_updates_per_sec=max_updates_per_sec)

  def _display(self):
    """ See Progress._display. """
    line = "%u" % (self._current_progress)
    print(line, flush=True)
    if self._additionnal_info is not None:
      print("# %s" % (self._additionnal_info), flush=True)

  def end(self):
    """ See Progress.end. """
    pass


class SimpleAnimatedProgress(Progress):

  """ Progress percentage display with animated scrobbler. """

  def __init__(self, *, max_updates_per_sec=10):
    super().__init__(max_updates_per_sec=max_updates_per_sec)
    self._scrobbler = itertools.cycle("|/-\\")

  def _display(self):
    """ See Progress._display. """
    line = "\r%s %u%%" % (next(self._scrobbler), self._current_progress)
    print(line, end="")
    if self._additionnal_info is not None:
      print(" %s" % (self._additionnal_info), end="")

  def end(self):
    """ See Progress.end. """
    print()
