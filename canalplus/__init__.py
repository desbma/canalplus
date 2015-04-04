#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Browse, play, or download CANAL+ videos. """

__version__ = "1.0.1"
__author__ = "desbma"
__license__ = "GPLv3"

import argparse
import itertools
import logging
import os
import shutil
import subprocess
import string
import sys
import tempfile
import urllib.parse
import xml.etree.ElementTree

import requests

from . import colored_logging
from . import progress_display


USER_AGENT = "Mozilla/5.0"


def format_byte_size_str(size):
  if size > 1000000000:
    return "%0.2fGB" % (size / 1000000000)
  elif size > 1000000:
    return "%0.2fMB" % (size / 1000000)
  elif size > 1000:
    return "%uKB" % (size // 1000)
  return "%uB" % (size)


class CanalPlusApiObject:

  BASE_URL = "http://service.canal-plus.com/video/rest"

  def fetchXml(self, action, parameter=""):
    """ Fetch XML data from an URL and return a xml.etree.ElementTree object. """
    url = "%s/%s/cplus/%s" % (self.BASE_URL, action, parameter)
    xml_text = self.fetchText(url)
    return xml.etree.ElementTree.fromstring(xml_text)

  def fetchText(self, url):
    """ Fetch text from an URL. """
    logging.getLogger().debug("Fetching '%s'..." % (url))
    response = requests.get(url, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.content.decode("utf-8")


class CanalPlusVideo(CanalPlusApiObject):

  def __init__(self, id, title):
    self.id = id
    self.title = title
    self.stream_url = None

  def download(self, dir):
    """ Download a video to a given directory. """
    logger = logging.getLogger()
    if self.stream_url is None:
      self.fetchVideoUrl()
    # sanitize output filename
    video_filepath = "%s.ts" % (self.title.replace("/", "-").strip(string.whitespace + "."))
    if os.path.isdir(dir):
      video_filepath = os.path.join(dir, video_filepath)
    # download
    if not os.path.isfile(video_filepath):
      show_progressbar = sys.stdout.isatty() and logging.getLogger().isEnabledFor(logging.INFO)
      if self.stream_url.endswith(".m3u8"):
        # fetch m3u8 playlist
        m3u8_data = self.fetchText(self.stream_url)
        # parse it
        ts_urls = tuple(filter(lambda x: not x.startswith("#"),
                               m3u8_data.splitlines()))
        # download ts files
        logging.getLogger().info("Downloading TS files...")
        if show_progressbar:
          progress = progress_display.ProgressBar()
        with tempfile.TemporaryDirectory() as temp_dir_path:
          ts_filepaths = []
          for i, ts_url in enumerate(ts_urls):
            ts_filepath = os.path.join(temp_dir_path, "%03u.ts" % (i + 1))
            with open(ts_filepath, "wb") as ts_file:
              response = requests.get(ts_url,
                                      stream=True,
                                      headers={"User-Agent": USER_AGENT})
              response.raise_for_status()
              total_size = int(response.headers["Content-Length"])
              for chunk in response.iter_content(2 ** 12):
                if show_progressbar:
                  downloaded_bytes = ts_file.tell()
                  progress.updateProgress((i * 100 / len(ts_urls)) +
                                          downloaded_bytes * (100 / len(ts_urls)) / total_size)
                  progress.setAdditionnalInfo("%s / %s (ts file %u/%u)" %
                                               (format_byte_size_str(downloaded_bytes),
                                                format_byte_size_str(total_size),
                                                i + 1,
                                                len(ts_urls)))
                  progress.display()
                ts_file.write(chunk)
            ts_filepaths.append(ts_filepath)
          if show_progressbar:
            progress.updateProgress(100)
            progress.display()
            progress.end()
          # concat files
          logging.getLogger().info("Concatenating TS files to '%s'..." % (video_filepath))
          with open(video_filepath, "wb") as video_file:
            for ts_filepath in ts_filepaths:
              with open(ts_filepath, "rb") as ts_file:
                shutil.copyfileobj(ts_file, video_file)

      else:  # direct stream download
        logging.getLogger().info("Downloading video to '%s'..." % (video_filepath))
        if show_progressbar:
          progress = progress_display.ProgressBar()
        with open(video_filepath, "wb") as video_file:
          response = requests.get(self.stream_url,
                                  stream=True,
                                  headers={"User-Agent": USER_AGENT})
          response.raise_for_status()
          total_size = int(response.headers["Content-Length"])
          for chunk in response.iter_content(2 ** 12):
            if show_progressbar:
              downloaded_bytes = video_file.tell()
              progress.updateProgress((i * 100 / len(ts_urls)) +
                                      downloaded_bytes * (100 / len(ts_urls)) / total_size)
              progress.setAdditionnalInfo("%s / %s (ts file %u/%u)" %
                                           (format_byte_size_str(downloaded_bytes),
                                            format_byte_size_str(total_size),
                                            i + 1,
                                            len(ts_urls)))
              progress.display()
            video_file.write(chunk)
          if show_progressbar:
            progress.updateProgress(100)
            progress.display()
            progress.end()
    else:
      logger.info("File '%s' already exists, skipping download" % (video_filepath))

  def view(self, player):
    """ View a video in a given media player. """
    logger = logging.getLogger()
    if self.stream_url is None:
      self.fetchVideoUrl()
    logger.info("Viewing in player '%s'..." % (player))
    player_cmd = (player, self.stream_url)
    if logger.isEnabledFor(logging.DEBUG):
      subprocess.check_call(player_cmd)
    else:
      subprocess.check_call(player_cmd,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

  def fetchVideoUrl(self):
    """ Fetch video URL for the best quality available. """
    # get video infos
    logging.getLogger().info("Getting video metadata...")
    xml_vidinfo = self.fetchXml("getVideos", self.id)
    playlist_url = xml_vidinfo.findtext("VIDEO/MEDIA/VIDEOS/HLS")
    if playlist_url:
      playlist = self.fetchText(playlist_url)
      self.stream_url = self.getPlaylistBestQuality(playlist)
    else:
      self.stream_url = xml_vidinfo.findtext("VIDEO/MEDIA/VIDEOS/HD")
      if not self.stream_url:
        self.stream_url = xml_vidinfo.findtext("VIDEO/MEDIA/VIDEOS/HAUT_DEBIT")
      if not self.stream_url:
        self.stream_url = xml_vidinfo.findtext("VIDEO/MEDIA/VIDEOS/BAS_DEBIT")
      assert(self.stream_url)

  def getPlaylistBestQuality(self, playlist):
    """ Parse an M3U8 playlist content, and return best quality stream. """
    highest_bitrate = 0
    best_quality_url = None
    streams = __class__.parseM3U(playlist)
    for url, attribs in streams:
      current_bitrate = int(attribs.partition("BANDWIDTH=")[2].split(",", 1)[0])
      logging.getLogger().debug("Got bitrate of %u" % (current_bitrate))
      if current_bitrate > highest_bitrate:
        highest_bitrate = current_bitrate
        best_quality_url = url
    assert(best_quality_url is not None)
    return best_quality_url

  @staticmethod
  def parseM3U(data):
    """ Parse M3U data and yield tuples of (url, attrib line str). """
    attrib_prefix = "#EXT-X-STREAM-INF"
    lines = data.splitlines()
    if lines[0] != "#EXTM3U":
      # not valid m3u
      return None
    attribs = None
    for line in lines[1:]:
      if line.startswith(attrib_prefix):
        attribs = line[len(attrib_prefix):]
      elif line.startswith("#"):
        # ignore
        continue
      else:
        # url
        yield (line, attribs)
        attribs = None


class CanalPlusProgram(CanalPlusApiObject):

  def __init__(self, id, title):
    self.id = id
    self.title = title
    self.xml_vidlist = None

  def __iter__(self):
    """ Get an iterator over program videos. """
    if self.xml_vidlist is None:
      self.fetchVidlist()
    return self.__next__()

  def __next__(self):
    """ Get a video. """
    for xml_vid in self.xml_vidlist.iterfind("MEA"):
      id = int(xml_vid.findtext("ID"))
      title = xml_vid.findtext("INFOS/TITRAGE/TITRE")
      subtitle = xml_vid.findtext("INFOS/TITRAGE/SOUS_TITRE")
      if subtitle:
        title = "%s (%s)" % (title, subtitle)
      yield CanalPlusVideo(id, title)

  def __getitem__(self, index):
    """ Get a video from the program at a given index. """
    if self.xml_vidlist is None:
      self.fetchVidlist()
    xml_vid = self.xml_vidlist.findall("MEA")[index]
    id = int(xml_vid.findtext("ID"))
    title = xml_vid.findtext("INFOS/TITRAGE/TITRE")
    subtitle = xml_vid.findtext("INFOS/TITRAGE/SOUS_TITRE")
    if subtitle:
      title = "%s (%s)" % (title, subtitle)
    return CanalPlusVideo(id, title)

  def __bool__(self):
    """ Return True if there is at least one video in the program, False otherwise. """
    if self.xml_vidlist is None:
      self.fetchVidlist()
    return self.xml_vidlist.find("MEA") is not None

  def __len__(self):
    """ Return the number of videos in the program. """
    if self.xml_vidlist is None:
      self.fetchVidlist()
    return len(self.xml_vidlist.iterfind("MEA"))

  def fetchVidlist(self):
    """ Fetch program video list. """
    # get videos list
    logging.getLogger().info("Getting video list...")
    self.xml_vidlist = self.fetchXml("getMEAs", self.id)


class CanalPlusSearch(CanalPlusApiObject):

  def __init__(self, query):
    self.query = query
    self.fetchVidlist()

  def __iter__(self):
    """ Get an iterator over search results. """
    return self.__next__()

  def __next__(self):
    """ Get a search result video. """
    for xml_vid in self.xml_vidlist.iterfind("VIDEO"):
      id = int(xml_vid.findtext("ID"))
      title = xml_vid.findtext("INFOS/TITRAGE/TITRE")
      subtitle = xml_vid.findtext("INFOS/TITRAGE/SOUS_TITRE")
      if subtitle:
        title = "%s (%s)" % (title, subtitle)
      yield CanalPlusVideo(id, title)

  def __getitem__(self, index):
    """ Get a video search result from a given index. """
    xml_vid = self.xml_vidlist.findall("VIDEO")[index]
    id = int(xml_vid.findtext("ID"))
    title = xml_vid.findtext("INFOS/TITRAGE/TITRE")
    subtitle = xml_vid.findtext("INFOS/TITRAGE/SOUS_TITRE")
    if subtitle:
      title = "%s (%s)" % (title, subtitle)
    return CanalPlusVideo(id, title)

  def __bool__(self):
    """ Return True if there is at least one search result, False otherwise. """
    return self.xml_vidlist.find("VIDEO") is not None

  def __len__(self):
    """ Return the number of search results. """
    return len(self.xml_vidlist.iterfind("VIDEO"))

  def fetchVidlist(self):
    """ Fetch search results list. """
    # get videos list
    logging.getLogger().info("Getting search results...")
    self.xml_vidlist = self.fetchXml("search", urllib.parse.quote_plus(self.query))


class CanalPlusProgramList(CanalPlusApiObject):

  def __init__(self):
    # get program list
    logging.getLogger().info("Getting program list...")

    xml_programs = self.fetchXml("initPlayer")
    # parse it
    self.programs = {}
    for xml_program_group in xml_programs.iterfind("THEMATIQUES/THEMATIQUE"):
      for xml_program in xml_program_group.iterfind("SELECTIONS/SELECTION"):
        id = int(xml_program.findtext("ID"))
        if id not in self.programs.keys():
          title = xml_program.findtext("NOM")
          self.programs[id] = title

  def __iter__(self):
    """ Get an iterator over programs. """
    return self.__next__()

  def __next__(self):
    """ Get a program. """
    for (id, title) in self.programs.items():
      yield CanalPlusProgram(id, title)

  def __len__(self):
    """ Get the number of programs. """
    return len(self.programs)

  def __contains__(self, title):
    """ Return True if a program with the given title is available, False otherwise. """
    for p in self:
      if p.title.lower() == title.lower():
        return True
    return False

  def __getitem__(self, key):
    """ Get a program from name or index. """
    if isinstance(key, str):
      for p in self:
        if p.title.lower() == key.lower():
          return p
    else:
      return next(itertools.islice(self, key, key + 1))


def cl_main():
  # parse args
  arg_parser = argparse.ArgumentParser(description=__doc__,
                                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  arg_parser.add_argument("output",
                          help="Output directory to put downloaded files. Use 'player:vlc' to stream in a player.")
  arg_parser.add_argument("-m",
                          "--mode",
                          choices=("auto", "last", "manual"),
                          default="manual",
                          dest="mode",
                          help="What to do with a program (download/view all videos, download/view only last video, \
                                interactively download/view a video")
  arg_parser.add_argument("-p",
                          "--program",
                          default=None,
                          dest="program",
                          help="Program (case insensitive). Use '?program' to do a search instead of looking for an \
                                exact match.")
  arg_parser.add_argument("-v",
                          "--verbose",
                          action="store_true",
                          default=False,
                          dest="verbose",
                          help="Increase program output")
  args = arg_parser.parse_args()

  # setup logger
  logger = logging.getLogger()
  if args.verbose:
    logger.setLevel(logging.DEBUG)
  else:
    logger.setLevel(logging.INFO)
  logging.getLogger("requests").setLevel(logging.ERROR)
  logging.getLogger("urllib3").setLevel(logging.ERROR)
  logging_formatter = colored_logging.ColoredFormatter(fmt="%(message)s")
  logging_handler = logging.StreamHandler()
  logging_handler.setFormatter(logging_formatter)
  logger.addHandler(logging_handler)

  # choose program
  if args.program is None:
    # interactive program selection mode
    programs = CanalPlusProgramList()
    for i, program in enumerate(programs, 1):
      print("% 3u. %s" % (i, string.capwords(program.title)))
    c = 0
    while c not in range(1, i + 1):
      try:
        c = int(input("? "))
      except ValueError:
        continue
      except KeyboardInterrupt:
        exit(130)
    program = programs[c - 1]
  elif args.program.startswith("?"):
    # program search mode
    program = CanalPlusSearch(args.program[1:])
  else:
    # exact program match mode
    programs = CanalPlusProgramList()
    if args.program in programs:
      program = programs[args.program]
    else:
      logger.error("Unknown program '%s'" % (args.program))
      exit(1)

  # choose vid(s) to download
  if args.mode == "auto":
    # auto mode
    logger.info("[Automatic mode] Getting all videos of program '%s'" % (program.title))
    for i, vid in enumerate(program, 1):
      logger.info("[Automatic mode] Getting video %u/%u : '%s'" % (i, len(program), vid.title))
      if args.output.startswith("player:"):
        vid.view(args.output.split(":", 1)[1])
      else:
        vid.download(args.output)
  elif args.mode == "last":
    # last video mode
    vid = next(iter(program))
    if isinstance(program, CanalPlusProgram):
      logger.info("[Last video mode] Getting last video of program '%s': '%s'" % (program.title, vid.title))
    else:
      logger.info("[Last video mode] Getting first search result for query '%s': '%s'" % (program.query, vid.title))
    if args.output.startswith("player:"):
      vid.view(args.output.split(":", 1)[1])
    else:
      vid.download(args.output)
  else:
    # interactive mode
    for i, vid in enumerate(program, 1):
      print("% 3u. %s" % (i, vid.title))
    if program:
      c = 0
      while c not in range(1, i + 1):
        try:
          c = int(input("? "))
        except ValueError:
          continue
        except KeyboardInterrupt:
          exit(130)
      vid = program[c - 1]
      if args.output.startswith("player:"):
        vid.view(args.output.split(":", 1)[1])
      else:
        vid.download(args.output)
    elif isinstance(program, CanalPlusProgram):
      logger.error("No videos for program '%s'" % (args.program))
      exit(1)
    else:
      logger.error("No videos for search '%s'" % (args.program[1:]))
      exit(1)


if __name__ == "__main__":
  cl_main()
