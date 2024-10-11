import urllib
import urllib.parse
from typing import TYPE_CHECKING, Dict, List, Literal, Tuple

import fsspec
import pandas as pd
from magicgui.widgets import ComboBox, Container, PushButton
from ome_zarr.io import parse_url
from ome_zarr.reader import Reader

if TYPE_CHECKING:
    import napari


class DataLoaderWidget(Container):

    ROYERLAB_DATA_URL = "https://public.czbiohub.org/royerlab"

    def __init__(self, viewer: "napari.viewer.Viewer"):
        super().__init__()
        # Create an HTTP file system
        self._viewer: napari.Viewer = viewer
        self._fs = fsspec.filesystem("http")

        self._images_url: Dict[str, str] = {}
        self._tracks_url: Dict[str, str] = {}

        self._fill_urls()

        self._images_combobox = ComboBox(
            name="Image",
            choices=sorted(self._images_url.keys()),
        )
        self.append(self._images_combobox)

        self._images_btn = PushButton(
            name="Load Image",
        )
        self._images_btn.changed.connect(self._on_image_btn_click)
        self.append(self._images_btn)

        self._tracks_combobox = ComboBox(
            name="Tracks",
            choices=sorted(self._tracks_url.keys()),
        )
        self.append(self._tracks_combobox)

        self._tracks_btn = PushButton(
            name="Load Tracks",
        )
        self._tracks_btn.changed.connect(self._on_tracks_btn_click)
        self.append(self._tracks_btn)

    @staticmethod
    def _parse_url(path: str) -> Tuple[str, str]:
        print(path)
        if path.endswith("/"):
            path = path[:-1]
        basename = urllib.parse.urlparse(path).path.split("/")[-1]
        try:
            stem, ext = basename.split(".", 1)
        except ValueError:
            stem, ext = basename, ""
        return stem, ext.lower()

    def _fill_urls(self) -> None:

        queue = [self.ROYERLAB_DATA_URL]

        while queue:
            path = queue.pop(0)
            dirs = self._iter_children(path, "directory")
            files = self._iter_children(path, "file")

            for f in files:
                stem, ext = self._parse_url(f)
                if ext == "csv":
                    self._tracks_url[stem] = f

            for d in dirs:
                if ".zarr" in d:
                    if self._is_ome_zarr(d):
                        stem, ext = self._parse_url(d)
                        self._images_url[stem] = urllib.parse.urljoin(path, d)
                elif ".." in d:
                    pass
                else:
                    queue.append(d)

    def _is_ome_zarr(self, path: str) -> bool:
        url = parse_url(path)
        if url is None:
            return False
        reader = Reader(url)
        try:
            node = next(reader())
        except StopIteration:
            return False
        return len(node.metadata) > 0

    def _on_image_btn_click(self) -> None:
        if self._images_combobox.value is None:
            return

        url = self._images_url[self._images_combobox.value]

        self._viewer.open(
            url,
            plugin="napari-ome-zarr",
        )

    def _on_tracks_btn_click(self) -> None:
        if self._tracks_combobox.value is None:
            return

        tracks_df = pd.read_csv(self._tracks_url[self._tracks_combobox.value])

        track_id_col = "track_id"
        if track_id_col not in tracks_df.columns:
            track_id_col = "TrackID"

        if "z" in tracks_df.columns:
            spatial_cols = ["z", "y", "x"]
        else:
            spatial_cols = ["y", "x"]

        self._viewer.add_tracks(
            tracks_df[[track_id_col, "t", *spatial_cols]],
            name=self._tracks_combobox.value,
        )

    def _iter_children(
        self,
        path: str,
        path_type: Literal["file", "directory"],
    ) -> List[str]:

        return [
            child["name"]
            for child in self._fs.ls(path)
            if child["type"] == path_type
        ]
