

"""
Parcel Map Manager
==================
Single-file PySide6 application for:
- displaying a real OpenStreetMap map;
- drawing parcels from manually entered coordinates;
- importing KML files;
- naming and saving parcels in SQLite;
- loading, renaming and deleting saved parcels.

Installation:
    py -m pip install PySide6 PySide6-WebEngine

Run:
    py parcel_map_manager.py

Note:
Internet access is required to load the map.
"""

from __future__ import annotations

import csv
import json
import math
import sqlite3
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineWidgets import QWebEngineView


APP_TITLE = "Digital  agronomist - Developed by Dr. Rositsa Cholakova & Eng. Simeon Nenov"
DB_FILENAME = "water_parcel_data.sqlite3"


def application_directory() -> Path:
    """
    Return a persistent application directory.
    - .py: directory containing this script
    - PyInstaller OneFile/OneDir: directory containing the executable
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


MAP_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Parcel Map</title>
  <link rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    html, body, #map { width: 100%; height: 100%; margin: 0; background: #111827; }
    .leaflet-container { font-family: Arial, sans-serif; }
    .parcel-label {
      color: #111827;
      background: rgba(255,255,255,.90);
      border: 1px solid rgba(17,24,39,.25);
      border-radius: 5px;
      padding: 2px 6px;
      font-weight: 700;
      box-shadow: 0 1px 3px rgba(0,0,0,.2);
    }
  </style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  const map = L.map('map', {zoomControl: true}).setView([42.6977, 23.3219], 7);

  // Leaflet inside QWebEngine sometimes needs an explicit resize pass.
  window.addEventListener('load', () => {
    setTimeout(() => map.invalidateSize(true), 150);
    setTimeout(() => map.invalidateSize(true), 700);
  });
  window.addEventListener('resize', () => map.invalidateSize(true));

  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 20,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  const parcelLayer = L.featureGroup().addTo(map);

  function clearParcels() {
    parcelLayer.clearLayers();
  }

  function showParcel(rings, name) {
    clearParcels();
    map.invalidateSize(true);
    if (!Array.isArray(rings) || rings.length === 0) return;

    const bounds = [];
    rings.forEach((ring) => {
      if (!Array.isArray(ring) || ring.length < 3) return;
      const polygon = L.polygon(ring, {
        color: '#f59e0b',
        weight: 4,
        opacity: 1,
        fillColor: '#22c55e',
        fillOpacity: 0.26
      }).addTo(parcelLayer);

      if (name) {
        polygon.bindTooltip(name, {
          permanent: true,
          direction: 'center',
          className: 'parcel-label'
        });
      }

      ring.forEach((point) => bounds.push(point));
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, {padding: [35, 35], maxZoom: 18});
    }
  }

  function setMapCenter(lat, lon, zoom) {
    map.setView([lat, lon], zoom || 15);
  }

  window.clearParcels = clearParcels;
  window.showParcel = showParcel;
  window.setMapCenter = setMapCenter;
</script>
</body>
</html>
"""


@dataclass
class ParcelRecord:
    parcel_id: int
    name: str
    rings: list[list[list[float]]]
    source: str
    created_at: str


class ParcelDatabase:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS parcels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                geometry_json TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS local_sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parcel_id INTEGER NOT NULL,
                measured_at TEXT NOT NULL,
                soil_moisture REAL, soil_temperature REAL, air_temperature REAL,
                relative_humidity REAL, rainfall REAL, wind_speed REAL,
                water_level REAL, flow_rate REAL, notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(parcel_id) REFERENCES parcels(id) ON DELETE CASCADE
            )
            """
        )
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.commit()

    def add_sensor_data(self, parcel_id, measured_at, values, notes):
        self.connection.execute(
            """INSERT INTO local_sensor_data(
            parcel_id, measured_at, soil_moisture, soil_temperature, air_temperature,
            relative_humidity, rainfall, wind_speed, water_level, flow_rate, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (parcel_id, measured_at, *values, notes),
        )
        self.connection.commit()

    def get_sensor_data(self, parcel_id=None):
        sql = """SELECT s.id,p.name,s.measured_at,s.soil_moisture,s.soil_temperature,
        s.air_temperature,s.relative_humidity,s.rainfall,s.wind_speed,s.water_level,
        s.flow_rate,s.notes FROM local_sensor_data s JOIN parcels p ON p.id=s.parcel_id"""
        params = ()
        if parcel_id is not None:
            sql += " WHERE s.parcel_id=?"
            params = (parcel_id,)
        sql += " ORDER BY s.measured_at DESC, s.id DESC"
        return self.connection.execute(sql, params).fetchall()

    def delete_sensor_data(self, record_id):
        self.connection.execute("DELETE FROM local_sensor_data WHERE id=?", (record_id,))
        self.connection.commit()

    def list_parcels(self) -> list[ParcelRecord]:
        rows = self.connection.execute(
            """
            SELECT id, name, geometry_json, source, created_at
            FROM parcels
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()
        return [
            ParcelRecord(
                parcel_id=int(row["id"]),
                name=str(row["name"]),
                rings=json.loads(row["geometry_json"]),
                source=str(row["source"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def save_parcel(
        self,
        name: str,
        rings: list[list[list[float]]],
        source: str,
        parcel_id: int | None = None,
    ) -> int:
        geometry_json = json.dumps(rings, ensure_ascii=False, separators=(",", ":"))

        if parcel_id is None:
            cursor = self.connection.execute(
                """
                INSERT INTO parcels(name, geometry_json, source)
                VALUES (?, ?, ?)
                """,
                (name, geometry_json, source),
            )
            self.connection.commit()
            return int(cursor.lastrowid)

        self.connection.execute(
            """
            UPDATE parcels
            SET name = ?,
                geometry_json = ?,
                source = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name, geometry_json, source, parcel_id),
        )
        self.connection.commit()
        return parcel_id

    def rename_parcel(self, parcel_id: int, new_name: str) -> None:
        self.connection.execute(
            """
            UPDATE parcels
            SET name = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_name, parcel_id),
        )
        self.connection.commit()

    def delete_parcel(self, parcel_id: int) -> None:
        self.connection.execute("DELETE FROM parcels WHERE id = ?", (parcel_id,))
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def remove_duplicate_closing_point(
    ring: list[list[float]],
) -> list[list[float]]:
    if len(ring) >= 2 and ring[0] == ring[-1]:
        return ring[:-1]
    return ring


def validate_rings(rings: list[list[list[float]]]) -> None:
    if not rings:
        raise ValueError("No parcel coordinates were found.")

    for index, ring in enumerate(rings, start=1):
        if len(ring) < 3:
            raise ValueError(
                f"Contour {index} has only {len(ring)} points. At least three points are required."
            )

        for point in ring:
            if len(point) != 2:
                raise ValueError("Invalid coordinate point.")
            lat, lon = point
            if not -90.0 <= lat <= 90.0:
                raise ValueError(f"Invalid latitude: {lat}")
            if not -180.0 <= lon <= 180.0:
                raise ValueError(f"Invalid longitude: {lon}")


def parse_kml_file(file_path: Path) -> list[list[list[float]]]:
    try:
        tree = ET.parse(file_path)
    except ET.ParseError as exc:
        raise ValueError(f"The KML file is not valid XML: {exc}") from exc

    root = tree.getroot()
    rings: list[list[list[float]]] = []


    for coordinates_element in root.iter():
        local_name = coordinates_element.tag.split("}")[-1]
        if local_name != "coordinates":
            continue

        parent_local_names = []

        text = (coordinates_element.text or "").strip()
        if not text:
            continue

        ring: list[list[float]] = []
        for token in text.replace("\n", " ").replace("\t", " ").split():
            parts = token.split(",")
            if len(parts) < 2:
                continue
            try:
                lon = float(parts[0])
                lat = float(parts[1])
            except ValueError:
                continue
            ring.append([lat, lon])

        ring = remove_duplicate_closing_point(ring)
        if len(ring) >= 3:
            rings.append(ring)

    validate_rings(rings)
    return rings


def parse_manual_coordinates(
    text: str,
    order: str,
) -> list[list[list[float]]]:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Enter parcel coordinates.")

    points: list[list[float]] = []
    rows = cleaned.replace(";", "\n").splitlines()

    for line_number, row in enumerate(rows, start=1):
        row = row.strip()
        if not row:
            continue

        normalized = row.replace("\t", " ").replace(",", " ")
        values = [value for value in normalized.split() if value]
        if len(values) < 2:
            raise ValueError(
                f"Line {line_number} does not contain two coordinates: {row}"
            )

        try:
            first = float(values[0])
            second = float(values[1])
        except ValueError as exc:
            raise ValueError(
                f"Line {line_number} contains an invalid number: {row}"
            ) from exc

        if order == "lat_lon":
            lat, lon = first, second
        else:
            lon, lat = first, second

        points.append([lat, lon])

    points = remove_duplicate_closing_point(points)
    rings = [points]
    validate_rings(rings)
    return rings


def haversine_distance_m(point_a: list[float], point_b: list[float]) -> float:
    lat1, lon1 = map(math.radians, point_a)
    lat2, lon2 = map(math.radians, point_b)
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2.0) ** 2
    )
    return 2 * 6371008.8 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def polygon_area_m2(ring: list[list[float]]) -> float:
    """
    Approximate area using a local equal-area projection.
    Suitable for relatively small land parcels.
    """
    if len(ring) < 3:
        return 0.0

    mean_lat = math.radians(sum(point[0] for point in ring) / len(ring))
    radius = 6371008.8

    xy = []
    for lat, lon in ring:
        x = radius * math.radians(lon) * math.cos(mean_lat)
        y = radius * math.radians(lat)
        xy.append((x, y))

    area = 0.0
    for index, (x1, y1) in enumerate(xy):
        x2, y2 = xy[(index + 1) % len(xy)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def total_area_m2(rings: Iterable[list[list[float]]]) -> float:
    return sum(polygon_area_m2(ring) for ring in rings)


class NameDialog(QDialog):
    def __init__(
        self,
        title: str,
        initial_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)

        self.name_edit = QLineEdit(initial_name)
        self.name_edit.setPlaceholderText("Example: North water parcel 01")

        form = QFormLayout()
        form.addRow("Parcel name:", self.name_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def parcel_name(self) -> str:
        return self.name_edit.text().strip()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.db = ParcelDatabase(application_directory() / DB_FILENAME)
        self.current_rings = []
        self.current_source = "manual"
        self.current_parcel_id = None
        self.current_name = ""
        self.map_ready = False

        self.setWindowTitle(APP_TITLE)
        self.resize(1400, 850)
        self.setMinimumSize(1000, 650)

        self._build_ui()
        self._build_menu()
        self._apply_theme()
        self._load_map()
        self.refresh_saved_parcels()
        self._refresh_parcel_combos()
        self._refresh_sensor_table()

    def _build_ui(self) -> None:
        root_splitter = QSplitter(Qt.Orientation.Horizontal)

        controls = QWidget()
        controls.setMinimumWidth(350)
        controls.setMaximumWidth(480)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Water-management parcels")
        title.setObjectName("titleLabel")
        controls_layout.addWidget(title)

        explanation = QLabel(
            "Import a KML file or enter coordinates. Draw the parcel on the real map, "
            "name it and save it in SQLite."
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("secondaryLabel")
        controls_layout.addWidget(explanation)

        self.tabs = QTabWidget()

        manual_tab = QWidget()
        manual_layout = QVBoxLayout(manual_tab)

        manual_help = QLabel(
            "Enter one point per line or separate points with semicolons.\n"
            "Example:\n"
            "42.123456, 27.123456\n42.124000, 27.125000\n42.122500, 27.126500"
        )
        manual_help.setWordWrap(True)
        manual_help.setObjectName("secondaryLabel")
        manual_layout.addWidget(manual_help)

        self.coordinate_order = QComboBox()
        self.coordinate_order.addItem(
            "Latitude, Longitude", "lat_lon"
        )
        self.coordinate_order.addItem(
            "Longitude, Latitude", "lon_lat"
        )
        manual_layout.addWidget(self.coordinate_order)

        self.coordinates_edit = QTextEdit()
        self.coordinates_edit.setPlaceholderText(
            "42.123456, 27.123456\n"
            "42.124000, 27.125000\n"
            "42.122500, 27.126500"
        )
        manual_layout.addWidget(self.coordinates_edit, 1)

        draw_manual_button = QPushButton("DRAW FROM COORDINATES")
        draw_manual_button.clicked.connect(self.draw_manual_coordinates)
        manual_layout.addWidget(draw_manual_button)

        kml_tab = QWidget()
        kml_layout = QVBoxLayout(kml_tab)

        kml_help = QLabel(
            "Standard KML Polygon and LinearRing coordinates are supported. "
            "All detected contours are stored as one parcel record."
        )
        kml_help.setWordWrap(True)
        kml_help.setObjectName("secondaryLabel")
        kml_layout.addWidget(kml_help)

        self.kml_path_edit = QLineEdit()
        self.kml_path_edit.setReadOnly(True)
        self.kml_path_edit.setPlaceholderText("No KML file selected")
        kml_layout.addWidget(self.kml_path_edit)

        choose_kml_button = QPushButton("SELECT .KML FILE")
        choose_kml_button.clicked.connect(self.choose_kml)
        kml_layout.addWidget(choose_kml_button)

        self.import_kml_button = QPushButton("DRAW KML PARCEL")
        self.import_kml_button.clicked.connect(self.draw_selected_kml)
        self.import_kml_button.setEnabled(False)
        kml_layout.addWidget(self.import_kml_button)
        kml_layout.addStretch(1)

        self.tabs.addTab(manual_tab, "Coordinates")
        self.tabs.addTab(kml_tab, "KML file")
        controls_layout.addWidget(self.tabs, 3)

        self.info_label = QLabel("No parcel is loaded.")
        self.info_label.setWordWrap(True)
        self.info_label.setObjectName("infoLabel")
        controls_layout.addWidget(self.info_label)

        action_row = QHBoxLayout()
        self.save_button = QPushButton("SAVE TO DATABASE")
        self.save_button.clicked.connect(self.save_current_parcel)
        self.save_button.setEnabled(False)
        action_row.addWidget(self.save_button)

        clear_button = QPushButton("CLEAR")
        clear_button.clicked.connect(self.clear_current_parcel)
        action_row.addWidget(clear_button)
        controls_layout.addLayout(action_row)

        saved_label = QLabel("Saved parcels")
        saved_label.setObjectName("sectionLabel")
        controls_layout.addWidget(saved_label)

        self.parcel_list = QListWidget()
        self.parcel_list.itemDoubleClicked.connect(self.load_selected_parcel)
        controls_layout.addWidget(self.parcel_list, 2)

        database_buttons = QHBoxLayout()

        load_button = QPushButton("LOAD")
        load_button.clicked.connect(self.load_selected_parcel)
        database_buttons.addWidget(load_button)

        rename_button = QPushButton("RENAME")
        rename_button.clicked.connect(self.rename_selected_parcel)
        database_buttons.addWidget(rename_button)

        delete_button = QPushButton("DELETE")
        delete_button.clicked.connect(self.delete_selected_parcel)
        database_buttons.addWidget(delete_button)

        controls_layout.addLayout(database_buttons)

        self.map_view = QWebEngineView()
        self.map_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.map_view.loadFinished.connect(self._on_map_loaded)

        root_splitter.addWidget(controls)
        root_splitter.addWidget(self.map_view)
        root_splitter.setStretchFactor(0, 0)
        root_splitter.setStretchFactor(1, 1)
        root_splitter.setSizes([410, 990])

        parcel_page = QWidget()
        parcel_layout = QVBoxLayout(parcel_page)
        parcel_layout.setContentsMargins(0, 0, 0, 0)
        parcel_layout.addWidget(root_splitter)

        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(parcel_page, "Parcel map")
        self.main_tabs.addTab(self._build_platform_data_tab(), "Platform data")
        self.main_tabs.addTab(self._build_local_sensor_tab(), "Local censors data")
        self.main_tabs.currentChanged.connect(
            lambda _i: QTimer.singleShot(150, lambda: self._run_js("map.invalidateSize(true);"))
        )

        self.setCentralWidget(self.main_tabs)
        self.statusBar().showMessage("Ready")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        open_action = QAction("Open KML", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.choose_kml)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = self.menuBar().addMenu("Map")

        home_action = QAction("Show Bulgaria", self)
        home_action.triggered.connect(
            lambda: self._run_js("setMapCenter(42.7339, 25.4858, 7);")
        )
        view_menu.addAction(home_action)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background-color: #111827;
                color: #e5e7eb;
            }
            QMenuBar, QMenu {
                background-color: #111827;
                color: #e5e7eb;
            }
            QMenu::item:selected {
                background-color: #374151;
            }
            QLabel#titleLabel {
                font-size: 20px;
                font-weight: 700;
                color: #f9fafb;
            }
            QLabel#sectionLabel {
                font-size: 15px;
                font-weight: 700;
                color: #f9fafb;
                margin-top: 5px;
            }
            QLabel#secondaryLabel {
                color: #9ca3af;
            }
            QLabel#infoLabel {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 7px;
                padding: 9px;
                color: #d1d5db;
            }
            QLineEdit, QTextEdit, QComboBox, QListWidget, QTableWidget, QTabWidget::pane {
                background-color: #1f2937;
                color: #f3f4f6;
                border: 1px solid #4b5563;
                border-radius: 6px;
                padding: 5px;
                selection-background-color: #2563eb;
            }
            QTabBar::tab {
                background-color: #1f2937;
                color: #d1d5db;
                padding: 8px 14px;
                border: 1px solid #374151;
            }
            QTabBar::tab:selected {
                background-color: #374151;
                color: white;
            }
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 9px 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
            QListWidget::item {
                padding: 7px;
                border-bottom: 1px solid #374151;
            }
            QListWidget::item:selected {
                background-color: #2563eb;
            }
            QStatusBar {
                background-color: #0f172a;
                color: #cbd5e1;
            }
            """
        )

    def _load_map(self) -> None:
        self.map_view.setHtml(MAP_HTML)

    def _on_map_loaded(self, success: bool) -> None:
        self.map_ready = success
        if success:
            self.statusBar().showMessage("Map loaded")
            QTimer.singleShot(
                250,
                lambda: self._run_js("map.invalidateSize(true);"),
            )
            QTimer.singleShot(
                900,
                lambda: self._run_js("map.invalidateSize(true);"),
            )
            if self.current_rings:
                QTimer.singleShot(1000, self._show_current_on_map)
        else:
            self.statusBar().showMessage(
                "The map could not be loaded. Check the internet connection."
            )

    def _run_js(self, script: str) -> None:
        if not self.map_ready:
            self.statusBar().showMessage("The map is not ready yet.")
            return
        self.map_view.page().runJavaScript(script)

    def _show_current_on_map(self) -> None:
        rings_json = json.dumps(self.current_rings, ensure_ascii=False)
        name_json = json.dumps(self.current_name, ensure_ascii=False)
        self._run_js(f"showParcel({rings_json}, {name_json});")

    def _set_current_parcel(
        self,
        rings: list[list[list[float]]],
        source: str,
        name: str = "",
        parcel_id: int | None = None,
    ) -> None:
        validate_rings(rings)
        self.current_rings = rings
        self.current_source = source
        self.current_name = name
        self.current_parcel_id = parcel_id
        self.save_button.setEnabled(True)
        self._show_current_on_map()
        self._update_info()

    def _update_info(self) -> None:
        if not self.current_rings:
            self.info_label.setText("No parcel is loaded.")
            return

        point_count = sum(len(ring) for ring in self.current_rings)
        area_m2 = total_area_m2(self.current_rings)
        area_ha = area_m2 / 10000.0
        source_text = "KML" if self.current_source == "kml" else "coordinates"
        name_text = self.current_name or "unsaved parcel"

        self.info_label.setText(
            f"Parcel: {name_text}\nSource: "
            f"{source_text}\nContours: "
            f"{len(self.current_rings)} | Points: {point_count}\nApproximate area: "
            f"{area_m2:,.2f} m² / {area_ha:,.4f} ha"
        )

    def draw_manual_coordinates(self) -> None:
        try:
            rings = parse_manual_coordinates(
                self.coordinates_edit.toPlainText(),
                str(self.coordinate_order.currentData()),
            )
            self._set_current_parcel(rings, source="manual")
            self.statusBar().showMessage("Parcel drawn from coordinates.")
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid coordinates", str(exc))

    def choose_kml(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select KML file",
            str(Path.home()),
            "KML files (*.kml);;All files (*.*)",
        )
        if not file_name:
            return

        self.kml_path_edit.setText(file_name)
        self.import_kml_button.setEnabled(True)
        self.tabs.setCurrentIndex(1)

    def draw_selected_kml(self) -> None:
        file_path = Path(self.kml_path_edit.text().strip())
        if not file_path.is_file():
            QMessageBox.warning(self, "KML file", "The selected file does not exist.")
            return

        try:
            rings = parse_kml_file(file_path)
            self._set_current_parcel(rings, source="kml")
            self.statusBar().showMessage(
                f"KML parcel loaded: {file_path.name}"
            )
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "KML import error", str(exc))

    def save_current_parcel(self) -> None:
        if not self.current_rings:
            QMessageBox.information(
                self, "Save", "Draw or load a parcel first."
            )
            return

        dialog = NameDialog(
            "Save parcel",
            initial_name=self.current_name,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = dialog.parcel_name()
        if not name:
            QMessageBox.warning(self, "Name", "A parcel name is required.")
            return

        try:
            parcel_id = self.db.save_parcel(
                name=name,
                rings=self.current_rings,
                source=self.current_source,
                parcel_id=self.current_parcel_id,
            )
        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self,
                "Duplicate name",
                "A parcel with this name already exists. Choose another name.",
            )
            return
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Database error", str(exc))
            return

        self.current_parcel_id = parcel_id
        self.current_name = name
        self._show_current_on_map()
        self._update_info()
        self.refresh_saved_parcels(select_id=parcel_id)
        self._refresh_parcel_combos()
        self.statusBar().showMessage(f'Parcel "{name}" saved.')

    def refresh_saved_parcels(self, select_id: int | None = None) -> None:
        self.parcel_list.clear()
        try:
            records = self.db.list_parcels()
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Database error", str(exc))
            return

        for record in records:
            item = QListWidgetItem(record.name)
            item.setData(Qt.ItemDataRole.UserRole, record)
            item.setToolTip(
                f"Source: {record.source}\nCreated: {record.created_at}"
            )
            self.parcel_list.addItem(item)
            if select_id is not None and record.parcel_id == select_id:
                self.parcel_list.setCurrentItem(item)

    def selected_record(self) -> ParcelRecord | None:
        item = self.parcel_list.currentItem()
        if item is None:
            QMessageBox.information(
                self, "Selection", "Select a saved parcel from the list."
            )
            return None
        record = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(record, ParcelRecord):
            QMessageBox.warning(self, "Selection", "Invalid record.")
            return None
        return record

    def load_selected_parcel(self, _item: QListWidgetItem | None = None) -> None:
        record = self.selected_record()
        if record is None:
            return

        self._set_current_parcel(
            rings=record.rings,
            source=record.source,
            name=record.name,
            parcel_id=record.parcel_id,
        )

        if hasattr(self, "platform_parcel"):
            platform_index = self.platform_parcel.findData(record.parcel_id)
            if platform_index >= 0:
                self.platform_parcel.setCurrentIndex(platform_index)
        self.statusBar().showMessage(f'Parcel "{record.name}" loaded.')

    def rename_selected_parcel(self) -> None:
        record = self.selected_record()
        if record is None:
            return

        dialog = NameDialog(
            "Rename parcel",
            initial_name=record.name,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_name = dialog.parcel_name()
        if not new_name:
            QMessageBox.warning(self, "Name", "The name cannot be empty.")
            return

        try:
            self.db.rename_parcel(record.parcel_id, new_name)
        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self,
                "Duplicate name",
                "A parcel with this name already exists.",
            )
            return
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Database error", str(exc))
            return

        if self.current_parcel_id == record.parcel_id:
            self.current_name = new_name
            self._show_current_on_map()
            self._update_info()

        self.refresh_saved_parcels(select_id=record.parcel_id)
        self._refresh_parcel_combos()
        self.statusBar().showMessage(f'Parcel renamed to "{new_name}".')

    def delete_selected_parcel(self) -> None:
        record = self.selected_record()
        if record is None:
            return

        answer = QMessageBox.question(
            self,
            "Delete parcel",
            f"Delete parcel „{record.name}“?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.db.delete_parcel(record.parcel_id)
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Database error", str(exc))
            return

        if self.current_parcel_id == record.parcel_id:
            self.clear_current_parcel()

        self.refresh_saved_parcels()
        self._refresh_parcel_combos()
        self._refresh_sensor_table()
        self.statusBar().showMessage(f'Parcel "{record.name}" deleted.')

    def clear_current_parcel(self) -> None:
        self.current_rings = []
        self.current_source = "manual"
        self.current_parcel_id = None
        self.current_name = ""
        self.save_button.setEnabled(False)
        self.info_label.setText("No parcel is loaded.")
        self._run_js("clearParcels();")
        self.statusBar().showMessage("Current parcel cleared.")

    def _build_platform_data_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Platform data — selected parcel water statistics")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        note = QLabel(
            "This section does not read the METER.AC raw file. It is reserved for "
            "parcel-specific statistics retrieved from satellite and environmental "
            "platforms by clipping each dataset to the geometry of the selected parcel. "
            "Only water, wetness, soil moisture, water storage and supporting "
            "meteorological parameters are included."
        )
        note.setWordWrap(True)
        note.setObjectName("infoLabel")
        layout.addWidget(note)

        parcel_box = QGroupBox("Analysis parcel")
        parcel_layout = QHBoxLayout(parcel_box)

        parcel_layout.addWidget(QLabel("Selected parcel:"))
        self.platform_parcel = QComboBox()
        self.platform_parcel.currentIndexChanged.connect(
            self._update_platform_parcel_summary
        )
        parcel_layout.addWidget(self.platform_parcel, 1)

        use_current_button = QPushButton("USE CURRENT MAP PARCEL")
        use_current_button.clicked.connect(self._use_current_parcel_for_platform)
        parcel_layout.addWidget(use_current_button)

        layout.addWidget(parcel_box)

        self.platform_parcel_summary = QLabel(
            "No saved parcel is selected. Save or select a parcel before platform analysis."
        )
        self.platform_parcel_summary.setWordWrap(True)
        self.platform_parcel_summary.setObjectName("infoLabel")
        layout.addWidget(self.platform_parcel_summary)

        metrics_box = QGroupBox("Parcel-level platform statistics")
        metrics_layout = QVBoxLayout(metrics_box)

        self.platform_stats_table = QTableWidget(0, 10)
        self.platform_stats_table.setHorizontalHeaderLabels(
            [
                "Platform",
                "Parameter",
                "Period",
                "Samples",
                "Minimum",
                "Average",
                "Maximum",
                "Latest",
                "Coverage / quality",
                "Status",
            ]
        )
        self.platform_stats_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.platform_stats_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.platform_stats_table.verticalHeader().setVisible(False)

        header = self.platform_stats_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(4, 8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)

        metrics_layout.addWidget(self.platform_stats_table)

        self.platform_empty_label = QLabel(
            "No platform observations have been loaded for the selected parcel yet."
        )
        self.platform_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.platform_empty_label.setObjectName("secondaryLabel")
        metrics_layout.addWidget(self.platform_empty_label)

        layout.addWidget(metrics_box, 2)

        required_box = QGroupBox("Water-focused parameters to retrieve")
        required_layout = QVBoxLayout(required_box)

        self.platform_table = QTableWidget(0, 5)
        self.platform_table.setHorizontalHeaderLabels(
            ["Platform", "Parameter", "Unit", "Parcel statistic", "Engineering rule"]
        )

        rows = [
            (
                "Copernicus CLMS",
                "Surface Soil Moisture (SSM)",
                "% saturation",
                "Minimum, mean, maximum, latest and valid-pixel coverage",
                "Always store the uncertainty or noise information with the value",
            ),
            (
                "Copernicus CLMS",
                "Soil Water Index (SWI)",
                "index / %",
                "Mean and distribution for each available effective depth",
                "Use as stored/deeper-soil-water tendency, not as a local probe reading",
            ),
            (
                "Sentinel-1 SAR",
                "VV and VH backscatter",
                "dB",
                "Parcel mean, standard deviation and temporal change",
                "Backscatter is a model input and is not soil moisture by itself",
            ),
            (
                "Sentinel-1 SAR",
                "Derived soil-moisture estimate",
                "% or m³/m³",
                "Minimum, mean, maximum, latest and model confidence",
                "Only show after documented calibration and validation",
            ),
            (
                "Sentinel-2 L2A",
                "NDWI",
                "-1 to +1",
                "Mean, maximum and percentage of pixels above water threshold",
                "Apply cloud, shadow and snow masks before statistics",
            ),
            (
                "Sentinel-2 L2A",
                "MNDWI",
                "-1 to +1",
                "Mean and estimated open-water area inside the parcel",
                "Threshold must be locally validated",
            ),
            (
                "Sentinel-2 L2A",
                "NDMI",
                "-1 to +1",
                "Minimum, mean, maximum and temporal anomaly",
                "Report as moisture tendency, never as direct volumetric soil moisture",
            ),
            (
                "Sentinel-2 L2A",
                "Water / wet-area coverage",
                "% and ha",
                "Wet pixels divided by valid parcel pixels",
                "Display valid-pixel coverage and acquisition date",
            ),
            (
                "Meteorological platform",
                "Precipitation",
                "mm",
                "Daily, 7-day and 30-day accumulated rainfall",
                "Use the nearest suitable station or gridded parcel estimate",
            ),
            (
                "Meteorological platform",
                "Air temperature",
                "°C",
                "Minimum, mean and maximum for the selected period",
                "Required supporting input for water-loss calculations",
            ),
            (
                "Meteorological platform",
                "Relative humidity",
                "%",
                "Minimum, mean and maximum for the selected period",
                "Required for vapour-pressure deficit and evapotranspiration",
            ),
            (
                "Meteorological platform",
                "Wind speed",
                "m/s",
                "Mean, maximum and measurement height",
                "Required for evapotranspiration and irrigation-loss assessment",
            ),
            (
                "Meteorological platform",
                "Solar radiation",
                "MJ/m²/day",
                "Daily mean and accumulated energy",
                "Preferred for reference evapotranspiration",
            ),
            (
                "Calculated water balance",
                "Reference evapotranspiration ET0",
                "mm/day",
                "Daily value and accumulated period total",
                "Calculate only when the required meteorological inputs are available",
            ),
            (
                "Calculated water balance",
                "Parcel water balance",
                "mm",
                "Precipitation minus ET0 and known irrigation",
                "Clearly label missing irrigation, runoff and drainage inputs",
            ),
        ]

        self.platform_table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.platform_table.setItem(row_index, column_index, item)

        self.platform_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.platform_table.verticalHeader().setVisible(False)
        required_header = self.platform_table.horizontalHeader()
        required_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        required_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        required_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        required_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        required_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        required_layout.addWidget(self.platform_table)
        layout.addWidget(required_box, 2)
        return page

    def _use_current_parcel_for_platform(self) -> None:
        if self.current_parcel_id is None:
            QMessageBox.information(
                self,
                "Saved parcel required",
                "The parcel currently shown on the map must be saved before it can be "
                "used for platform statistics.",
            )
            return

        index = self.platform_parcel.findData(self.current_parcel_id)
        if index < 0:
            self._refresh_parcel_combos()
            index = self.platform_parcel.findData(self.current_parcel_id)

        if index >= 0:
            self.platform_parcel.setCurrentIndex(index)
            self._update_platform_parcel_summary()
            self.main_tabs.setCurrentIndex(1)

    def _update_platform_parcel_summary(self, _index: int | None = None) -> None:
        if not hasattr(self, "platform_parcel"):
            return

        parcel_id = self.platform_parcel.currentData()
        if parcel_id is None:
            self.platform_parcel_summary.setText(
                "No saved parcel is selected. Save or select a parcel before platform analysis."
            )

            self.platform_stats_table.setRowCount(0)
            self.platform_empty_label.setText(
                "No platform observations have been loaded for the selected parcel yet."
            )
            return

        try:
            records = self.db.list_parcels()
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Database error", str(exc))
            return

        record = next(
            (item for item in records if item.parcel_id == int(parcel_id)),
            None,
        )
        if record is None:
            self.platform_parcel_summary.setText("The selected parcel was not found.")
            return

        point_count = sum(len(ring) for ring in record.rings)
        area_m2 = total_area_m2(record.rings)
        area_ha = area_m2 / 10000.0

        all_points = [point for ring in record.rings for point in ring]
        min_lat = min(point[0] for point in all_points)
        max_lat = max(point[0] for point in all_points)
        min_lon = min(point[1] for point in all_points)
        max_lon = max(point[1] for point in all_points)

        self.platform_parcel_summary.setText(
            f'Parcel: "{record.name}" | Source: {record.source} | Contours: '
            f"{len(record.rings)} | Points: {point_count} | Area: "
            f"{area_ha:,.4f} ha | Bounding box: "
            f"{min_lat:.6f}, {min_lon:.6f} to "
            f"{max_lat:.6f}, {max_lon:.6f}"
        )

        perimeter_m = 0.0
        for ring in record.rings:
            if len(ring) < 2:
                continue
            for point_index, point in enumerate(ring):
                next_point = ring[(point_index + 1) % len(ring)]
                perimeter_m += haversine_distance_m(point, next_point)

        centroid_lat = sum(point[0] for point in all_points) / len(all_points)
        centroid_lon = sum(point[1] for point in all_points) / len(all_points)

        bbox_width_m = haversine_distance_m(
            [centroid_lat, min_lon],
            [centroid_lat, max_lon],
        )
        bbox_height_m = haversine_distance_m(
            [min_lat, centroid_lon],
            [max_lat, centroid_lon],
        )

        estimated_pixels_10m = max(1, round(area_m2 / 100.0))
        estimated_pixels_20m = max(1, round(area_m2 / 400.0))
        estimated_pixels_1km = area_m2 / 1_000_000.0

        geometry_rows = [
            (
                "Parcel geometry",
                "Area",
                "Current geometry",
                str(point_count),
                "",
                f"{area_ha:,.4f} ha",
                f"{area_m2:,.2f} m²",
                f"{area_ha:,.4f} ha",
                "Calculated from saved polygon coordinates",
                "READY",
            ),
            (
                "Parcel geometry",
                "Perimeter",
                "Current geometry",
                str(point_count),
                "",
                f"{perimeter_m:,.2f} m",
                "",
                f"{perimeter_m:,.2f} m",
                "Calculated geodesically from all contour edges",
                "READY",
            ),
            (
                "Parcel geometry",
                "Centroid",
                "Current geometry",
                str(point_count),
                f"{centroid_lat:.6f}",
                "",
                f"{centroid_lon:.6f}",
                f"{centroid_lat:.6f}, {centroid_lon:.6f}",
                "Arithmetic centroid of polygon vertices",
                "READY",
            ),
            (
                "Parcel geometry",
                "Bounding-box size",
                "Current geometry",
                "1",
                "",
                f"{bbox_width_m:,.1f} × {bbox_height_m:,.1f} m",
                "",
                f"{bbox_width_m:,.1f} × {bbox_height_m:,.1f} m",
                "Useful for platform request extent",
                "READY",
            ),
            (
                "Sentinel-2 readiness",
                "Estimated 10 m pixels",
                "Current geometry",
                str(estimated_pixels_10m),
                "",
                f"{estimated_pixels_10m:,}",
                "",
                f"{estimated_pixels_10m:,}",
                "Approximation from parcel area; actual valid pixels depend on raster alignment and masks",
                "READY",
            ),
            (
                "Sentinel-2 readiness",
                "Estimated 20 m pixels",
                "Current geometry",
                str(estimated_pixels_20m),
                "",
                f"{estimated_pixels_20m:,}",
                "",
                f"{estimated_pixels_20m:,}",
                "Approximation for SWIR-based water/moisture bands",
                "READY",
            ),
            (
                "Copernicus CLMS readiness",
                "Parcel fraction of one 1 km cell",
                "Current geometry",
                "1",
                "",
                f"{estimated_pixels_1km * 100.0:.4f} %",
                "",
                f"{estimated_pixels_1km:.6f} cell",
                "Small parcels may be below the effective resolution of 1 km products",
                "READY",
            ),
            (
                "Copernicus CLMS",
                "Surface Soil Moisture (SSM)",
                "Not requested yet",
                "0",
                "",
                "",
                "",
                "",
                "Requires an actual platform request clipped or sampled for this parcel",
                "PENDING DATA",
            ),
            (
                "Copernicus CLMS",
                "Soil Water Index (SWI)",
                "Not requested yet",
                "0",
                "",
                "",
                "",
                "",
                "Requires an actual platform request for the selected time period and depth",
                "PENDING DATA",
            ),
            (
                "Sentinel-1",
                "Soil-moisture model output",
                "Not requested yet",
                "0",
                "",
                "",
                "",
                "",
                "VV/VH scenes and a validated soil-moisture model are not connected yet",
                "PENDING DATA",
            ),
            (
                "Sentinel-2",
                "NDWI / MNDWI / NDMI",
                "Not requested yet",
                "0",
                "",
                "",
                "",
                "",
                "Optical scenes, cloud masks and acquisition dates are not connected yet",
                "PENDING DATA",
            ),
            (
                "Meteorological platform",
                "Rainfall / temperature / humidity / wind",
                "Not requested yet",
                "0",
                "",
                "",
                "",
                "",
                "A parcel-relevant station or gridded weather source is not connected yet",
                "PENDING DATA",
            ),
        ]

        self.platform_stats_table.setRowCount(len(geometry_rows))
        for row_index, row_values in enumerate(geometry_rows):
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.platform_stats_table.setItem(row_index, column_index, item)

        self.platform_empty_label.setText(
            f'Geometry statistics are available for parcel "{record.name}". '
            "Satellite and environmental values remain marked PENDING DATA until their "
            "APIs and time-period requests are connected. No values are fabricated."
        )

    def _build_local_sensor_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Local farmer sensor data by parcel")
        title.setObjectName("titleLabel")
        layout.addWidget(title)
        form_box = QGroupBox("New observation")
        grid = QGridLayout(form_box)
        self.sensor_parcel = QComboBox()
        grid.addWidget(QLabel("Parcel"), 0, 0)
        grid.addWidget(self.sensor_parcel, 0, 1)
        self.sensor_fields = {}
        fields = [
            ("soil_moisture", "Soil moisture %"), ("soil_temperature", "Soil temperature °C"),
            ("air_temperature", "Air temperature °C"), ("relative_humidity", "Relative humidity %"),
            ("rainfall", "Rainfall mm"), ("wind_speed", "Wind speed m/s"),
            ("water_level", "Water level m"), ("flow_rate", "Flow rate m³/h"),
        ]
        for i, (key, label) in enumerate(fields, 1):
            edit = QLineEdit()
            edit.setPlaceholderText("Optional")
            self.sensor_fields[key] = edit
            grid.addWidget(QLabel(label), i, 0)
            grid.addWidget(edit, i, 1)
        self.sensor_notes = QLineEdit()
        self.sensor_notes.setPlaceholderText("Sensor ID, depth, calibration or irrigation note")
        grid.addWidget(QLabel("Notes"), 9, 0)
        grid.addWidget(self.sensor_notes, 9, 1)
        save = QPushButton("SAVE OBSERVATION")
        save.clicked.connect(self._save_sensor_data)
        grid.addWidget(save, 10, 0, 1, 2)
        layout.addWidget(form_box)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Statistics and records for"))
        self.sensor_filter = QComboBox()
        self.sensor_filter.currentIndexChanged.connect(self._refresh_sensor_table)
        filter_row.addWidget(self.sensor_filter)
        self.sensor_stats = QLabel("No local sensor records.")
        self.sensor_stats.setObjectName("infoLabel")
        filter_row.addWidget(self.sensor_stats, 1)
        layout.addLayout(filter_row)
        self.sensor_table = QTableWidget(0, 12)
        self.sensor_table.setHorizontalHeaderLabels(["ID", "Parcel", "Measured at", "Soil moisture %", "Soil temp °C", "Air temp °C", "RH %", "Rainfall mm", "Wind m/s", "Water level m", "Flow m³/h", "Notes"])
        self.sensor_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sensor_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sensor_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.sensor_table, 1)
        delete = QPushButton("DELETE SELECTED OBSERVATION")
        delete.clicked.connect(self._delete_sensor_data)
        layout.addWidget(delete)
        return page

    def _refresh_parcel_combos(self) -> None:
        if not hasattr(self, "sensor_parcel"):
            return
        records = self.db.list_parcels()
        combo_configurations = [
            (self.sensor_parcel, False),
            (self.sensor_filter, True),
        ]
        if hasattr(self, "platform_parcel"):
            combo_configurations.append((self.platform_parcel, True))

        for combo, include_all in combo_configurations:
            selected = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            if include_all:
                combo.addItem("No parcel selected" if combo is getattr(self, "platform_parcel", None) else "All parcels", None)
            for record in records:
                combo.addItem(record.name, record.parcel_id)
            if selected is not None:
                idx = combo.findData(selected)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        if hasattr(self, "platform_parcel"):
            self._update_platform_parcel_summary()

    def _save_sensor_data(self) -> None:
        parcel_id = self.sensor_parcel.currentData()
        if parcel_id is None:
            QMessageBox.warning(self, "Parcel required", "Create and select a parcel first.")
            return
        values = []
        for edit in self.sensor_fields.values():
            text = edit.text().strip().replace(",", ".")
            if not text:
                values.append(None)
                continue
            try:
                values.append(float(text))
            except ValueError:
                QMessageBox.warning(self, "Invalid measurement", f'Invalid number: "{edit.text()}"')
                return
        if all(value is None for value in values):
            QMessageBox.warning(self, "No measurements", "Enter at least one numeric sensor value.")
            return
        self.db.add_sensor_data(int(parcel_id), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), values, self.sensor_notes.text().strip())
        for edit in self.sensor_fields.values():
            edit.clear()
        self.sensor_notes.clear()
        idx = self.sensor_filter.findData(parcel_id)
        if idx >= 0:
            self.sensor_filter.setCurrentIndex(idx)
        self._refresh_sensor_table()
        self.statusBar().showMessage("Local sensor observation saved.")

    def _refresh_sensor_table(self, _index=None) -> None:
        if not hasattr(self, "sensor_table"):
            return
        parcel_id = self.sensor_filter.currentData()
        rows = self.db.get_sensor_data(parcel_id)
        self.sensor_table.setRowCount(len(rows))
        numeric = [[] for _ in range(8)]
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self.sensor_table.setItem(r, c, QTableWidgetItem("" if value is None else str(value)))
            for i, value in enumerate(row[3:11]):
                if value is None:
                    continue
                numeric[i].append(float(value))
        names = ["soil moisture", "soil temperature", "air temperature", "relative humidity", "rainfall", "wind speed", "water level", "flow rate"]
        parts = []
        for name, values in zip(names, numeric):
            if not values:
                continue
            parts.append(f"{name}: avg {sum(values) / len(values):.2f}, min {min(values):.2f}, max {max(values):.2f}")
        self.sensor_stats.setText(" | ".join(parts) if parts else "No local sensor records.")

    def _delete_sensor_data(self) -> None:
        row = self.sensor_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Selection", "Select a sensor observation first.")
            return
        record_id = int(self.sensor_table.item(row, 0).text())
        answer = QMessageBox.question(self, "Delete observation", f"Delete observation ID {record_id}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.db.delete_sensor_data(record_id)
            self._refresh_sensor_table()

    def closeEvent(self, event) -> None:
        self.db.close()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("Simeon Nenov 2026")
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
