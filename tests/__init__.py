#!/usr/bin/env python3

import functools
import logging
import os
import random
import shutil
import tempfile
import unittest

import requests

import canalplus


class TestCanalPlus(unittest.TestCase):

  def checkIsVideo(self, video, *, download=True):
    self.assertIsInstance(video, canalplus.CanalPlusVideo)
    self.assertIsInstance(video.title, str)
    self.assertTrue(video.title)
    self.assertTrue(video.stream_url.startswith("http"))
    if video.stream_url.endswith(".m3u8"):
      m3u_data = requests.get(video.stream_url).text
      streams = tuple(canalplus.CanalPlusVideo.parseM3U(m3u_data))
      self.assertGreaterEqual(len(streams), 1)
      for stream in streams:
        if stream[0].endswith(".m3u8"):
          self.assertGreaterEqual(len(streams), 3)  # 3 qualities
          m3u_data = requests.get(stream[0]).text
          media_streams = tuple(canalplus.CanalPlusVideo.parseM3U(m3u_data))
          # each ts file is 10s long, assume no video is shorter than 30s
          self.assertGreaterEqual(len(media_streams), 3)
    if download:
      with tempfile.TemporaryDirectory() as temp_dir_path:
        video.download(temp_dir_path)
        downloaded = tuple(map(functools.partial(os.path.join, temp_dir_path),
                               os.listdir(temp_dir_path)))
        self.assertEqual(len(downloaded), 1)
        self.assertTrue(os.path.isfile(downloaded[0]))
        self.assertGreaterEqual(os.path.getsize(downloaded[0]), 0)
    if shutil.which("true") is not None:
      video.view("true")

  def test_getProgramList(self):
    """ Get program list, check expected programs and download a video. """
    programs = canalplus.CanalPlusProgramList()
    self.assertGreaterEqual(len(programs), 40)
    for program in programs:
      self.assertIsInstance(program, canalplus.CanalPlusProgram)
      #self.assertTrue(program)
      self.assertIsInstance(program.title, str)
      self.assertTrue(program.title)
    self.assertIn("divertissement", programs)
    self.assertIn("BANDES ANNONCES FILMS DIFFUSES SUR CANAL+", programs)
    if False:  # slow!
      for program in programs:
        for video in program:
          video.fetchVideoUrl()
          self.checkIsVideo(video, download=False)
    else:
      programs = tuple(programs)
      program = None
      while not program:
        program = random.choice(programs)
      video = random.choice(tuple(program))
      video.fetchVideoUrl()
      self.checkIsVideo(video)

  def test_search(self):
    """ Search for a program, and download a search result. """
    videos = canalplus.CanalPlusSearch("les guignols")
    videos = tuple(videos)
    self.assertGreaterEqual(len(videos), 40)
    video = random.choice(videos)
    video.fetchVideoUrl()
    self.checkIsVideo(video)


if __name__ == "__main__":
  # disable logging
  logging.basicConfig(level=logging.CRITICAL + 1)
  #logging.basicConfig(level=logging.DEBUG)

  # run tests
  unittest.main()
