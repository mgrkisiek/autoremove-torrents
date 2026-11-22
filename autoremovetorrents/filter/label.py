#-*- coding:utf-8 -*-

from .filter import Filter

class LabelFilter(Filter):
    def __init__(self, all_label, ac, re):
        Filter.__init__(self, all_label, ac, re)
        # Labels are compared as strings
        self._accept = set(str(x) for x in self._accept)
        self._reject = set(str(x) for x in self._reject)

    @staticmethod
    def _labels(torrent):
        # Torrents from clients without label support have no labels
        return getattr(torrent, 'label', None) or []

    def apply(self, torrents):
        # Pick accepted torrents
        accepts = set()
        if self._all: # Accept all torrents (all_labels)
            accepts = set(torrents)
        elif len(self._accept) > 0: # Accept torrents having any of these labels (labels)
            for torrent in torrents:
                if any(label in self._accept for label in LabelFilter._labels(torrent)):
                    accepts.add(torrent)
        # Pick rejected torrents (excluded_labels)
        rejects = set()
        if len(self._reject) > 0:
            for torrent in accepts:
                if any(label in self._reject for label in LabelFilter._labels(torrent)):
                    rejects.add(torrent)
        return accepts.difference(rejects) # Return their difference
