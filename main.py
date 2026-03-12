import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from pyvistaqt import QtInteractor

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from solver import solve_thermal_field, extract_centerline_profile


class TemperaturePlotCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.figure = Figure(figsize=(4, 3), tight_layout=True)
        self.ax = self.figure.add_subplot(111)
        super().__init__(self.figure)
        self.setParent(parent)

    def plot_profile(self, x, t):
        self.ax.clear()
        self.ax.plot(x, t, linewidth=2)
        self.ax.set_title("Centerline Temperature Profile")
        self.ax.set_xlabel("x (um)")
        self.ax.set_ylabel("Temperature (K)")
        self.ax.grid(True, alpha=0.3)
        self.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MEMS Chip Thermal Demo - Version 3")
        self.resize(1600, 900)

        self.current_project_path = None

        self._build_ui()
        self._create_menu()
        self.statusBar().showMessage("Ready")
        self._show_initial_geometry()

    # ----------------------------
    # UI
    # ----------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        left_panel = self._build_left_panel()
        center_panel = self._build_center_panel()
        right_panel = self._build_right_panel()

        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(center_panel, 6)
        main_layout.addWidget(right_panel, 3)

    def _build_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # Geometry
        geom_group = QGroupBox("Geometry Parameters")
        geom_form = QFormLayout()

        self.length_spin = self._make_spinbox(1000.0, 10.0, 5000.0, 1.0)
        self.width_spin = self._make_spinbox(1000.0, 1.0, 1000.0, 1.0)
        self.thickness_spin = self._make_spinbox(50.0, 1.0, 500.0, 1.0)

        geom_form.addRow("Length L (um)", self.length_spin)
        geom_form.addRow("Width W (um)", self.width_spin)
        geom_form.addRow("Thickness T (um)", self.thickness_spin)
        geom_group.setLayout(geom_form)

        # Material
        material_group = QGroupBox("Material Parameters")
        material_form = QFormLayout()

        self.k_spin = self._make_spinbox(150.0, 0.1, 10000.0, 1.0)
        material_form.addRow("Thermal k (W/mK)", self.k_spin)
        material_group.setLayout(material_form)

        # Boundary
        drive_group = QGroupBox("Drive / Boundary")
        drive_form = QFormLayout()

        self.voltage_spin = self._make_spinbox(5.0, 0.0, 100.0, 0.1)
        self.boundary_temp_spin = self._make_spinbox(300.0, 0.0, 2000.0, 1.0)

        drive_form.addRow("Voltage V (V)", self.voltage_spin)
        drive_form.addRow("Boundary Temp (K)", self.boundary_temp_spin)
        drive_group.setLayout(drive_form)

        # Mesh / Display
        display_group = QGroupBox("Mesh / Display")
        display_form = QFormLayout()

        self.mesh_combo = QComboBox()
        self.mesh_combo.addItems(["Coarse", "Medium", "Fine"])
        self.mesh_combo.setCurrentText("Medium")

        self.slice_combo = QComboBox()
        self.slice_combo.addItems(["Off", "Mid-X Slice"])
        self.slice_combo.setCurrentText("Mid-X Slice")

        display_form.addRow("Mesh Density", self.mesh_combo)
        display_form.addRow("Slice Display", self.slice_combo)
        display_group.setLayout(display_form)

        # Actions
        action_group = QGroupBox("Actions")
        action_layout = QVBoxLayout()

        self.calc_button = QPushButton("Calculate")
        self.reset_button = QPushButton("Reset")
        self.save_button = QPushButton("Save Parameters")
        self.load_button = QPushButton("Load Parameters")

        self.calc_button.clicked.connect(self.calculate_and_render)
        self.reset_button.clicked.connect(self.reset_parameters)
        self.save_button.clicked.connect(self.save_parameters)
        self.load_button.clicked.connect(self.load_parameters)

        action_layout.addWidget(self.calc_button)
        action_layout.addWidget(self.reset_button)
        action_layout.addWidget(self.save_button)
        action_layout.addWidget(self.load_button)
        action_group.setLayout(action_layout)

        layout.addWidget(geom_group)
        layout.addWidget(material_group)
        layout.addWidget(drive_group)
        layout.addWidget(display_group)
        layout.addWidget(action_group)
        layout.addStretch()

        return panel

    def _build_center_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.plotter = QtInteractor(self)
        self.plotter.set_background("white")

        layout.addWidget(self.plotter.interactor)
        return panel

    def _build_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        title = QLabel("Results & Analysis")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        splitter = QSplitter(Qt.Vertical)

        # 上半：文本结果
        upper_widget = QWidget()
        upper_layout = QVBoxLayout(upper_widget)
        upper_layout.setContentsMargins(0, 0, 0, 0)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        upper_layout.addWidget(self.result_text)

        # 下半：温度曲线
        lower_widget = QWidget()
        lower_layout = QVBoxLayout(lower_widget)
        lower_layout.setContentsMargins(0, 0, 0, 0)

        self.profile_canvas = TemperaturePlotCanvas(self)
        lower_layout.addWidget(self.profile_canvas)

        splitter.addWidget(upper_widget)
        splitter.addWidget(lower_widget)
        splitter.setSizes([420, 280])

        info_box = QFrame()
        info_box.setFrameShape(QFrame.StyledPanel)
        info_layout = QVBoxLayout(info_box)

        tip_title = QLabel("Usage")
        tip_title.setStyleSheet("font-weight: bold;")

        tip_text = QLabel(
            "1. Modify parameters on the left\n"
            "2. Choose mesh density\n"
            "3. Click Calculate\n"
            "4. Rotate / zoom the 3D model\n"
            "5. Inspect the centerline temperature profile"
        )
        tip_text.setWordWrap(True)

        info_layout.addWidget(tip_title)
        info_layout.addWidget(tip_text)

        layout.addWidget(title)
        layout.addWidget(splitter, 1)
        layout.addWidget(info_box)

        return panel

    def _create_menu(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        save_action = file_menu.addAction("Save Parameters")
        load_action = file_menu.addAction("Load Parameters")
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")

        save_action.triggered.connect(self.save_parameters)
        load_action.triggered.connect(self.load_parameters)
        exit_action.triggered.connect(self.close)

        view_menu = menu_bar.addMenu("View")
        reset_camera_action = view_menu.addAction("Reset Camera")
        show_outline_action = view_menu.addAction("Show Initial Geometry")

        reset_camera_action.triggered.connect(self._reset_camera)
        show_outline_action.triggered.connect(self._show_initial_geometry)

        help_menu = menu_bar.addMenu("Help")
        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self.show_about_dialog)

    def _make_spinbox(self, value, min_val, max_val, step):
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(value)
        spin.setSingleStep(step)
        spin.setDecimals(3)
        return spin

    # ----------------------------
    # Parameters / mesh
    # ----------------------------
    def _get_parameters(self):
        return {
            "L": self.length_spin.value(),
            "W": self.width_spin.value(),
            "T": self.thickness_spin.value(),
            "k": self.k_spin.value(),
            "V": self.voltage_spin.value(),
            "T_boundary": self.boundary_temp_spin.value(),
        }

    def _set_parameters(self, params):
        self.length_spin.setValue(float(params.get("L", 200.0)))
        self.width_spin.setValue(float(params.get("W", 20.0)))
        self.thickness_spin.setValue(float(params.get("T", 10.0)))
        self.k_spin.setValue(float(params.get("k", 150.0)))
        self.voltage_spin.setValue(float(params.get("V", 5.0)))
        self.boundary_temp_spin.setValue(float(params.get("T_boundary", 300.0)))

        mesh_name = params.get("mesh_density", "Medium")
        if mesh_name in ["Coarse", "Medium", "Fine"]:
            self.mesh_combo.setCurrentText(mesh_name)

        slice_name = params.get("slice_display", "Mid-X Slice")
        if slice_name in ["Off", "Mid-X Slice"]:
            self.slice_combo.setCurrentText(slice_name)

    def _get_mesh_resolution(self):
        mesh_name = self.mesh_combo.currentText()
        if mesh_name == "Coarse":
            return 24, 10, 6
        if mesh_name == "Fine":
            return 60, 24, 14
        return 40, 16, 10

    # ----------------------------
    # Rendering
    # ----------------------------
    def _show_initial_geometry(self):
        params = self._get_parameters()
        self.statusBar().showMessage("Loading initial geometry...")

        try:
            nx, ny, nz = self._get_mesh_resolution()
            grid, stats = solve_thermal_field(**params, nx=nx, ny=ny, nz=nz)

            self.plotter.clear()
            self.plotter.add_mesh(grid.outline(), color="black", line_width=2)
            self.plotter.add_axes()
            self.plotter.add_text("Initial MEMS Chip Geometry", font_size=12)
            self._set_good_camera_view()
            self._update_result_text(params, stats, mode="initial")
            self._update_profile_plot(grid)

            self.statusBar().showMessage("Initial chip geometry loaded")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to initialize geometry:\n{exc}")
            self.statusBar().showMessage("Initialization failed")

    def calculate_and_render(self):
        params = self._get_parameters()
        self.statusBar().showMessage("Calculating thermal field...")

        try:
            nx, ny, nz = self._get_mesh_resolution()
            grid, stats = solve_thermal_field(**params, nx=nx, ny=ny, nz=nz)

            self.plotter.clear()

            self.plotter.add_mesh(
                grid,
                scalars="Temperature",
                show_edges=False,
                smooth_shading=True,
                scalar_bar_args={
                    "title": "Temperature (K)",
                    "vertical": False,
                    "position_x": 0.35,
                    "position_y": 0.02,
                    "width": 0.42,
                    "height": 0.06,
                    "fmt": "%.0f",
                },
                cmap="jet",
            )

            self.plotter.add_mesh(
                grid.outline(),
                color="black",
                line_width=1.2,
            )

            if self.slice_combo.currentText() == "Mid-X Slice":
                mid_x = params["L"] / 2.0
                slice_mesh = grid.slice(normal=(1, 0, 0), origin=(mid_x, 0, 0))
                self.plotter.add_mesh(
                    slice_mesh,
                    scalars="Temperature",
                    cmap="jet",
                    opacity=0.95,
                    show_scalar_bar=False,
                )

            self.plotter.add_axes()
            self.plotter.add_text("MEMS Chip Temperature Field", font_size=12)

            self._set_good_camera_view()
            self._update_result_text(params, stats, mode="calculated")
            self._update_profile_plot(grid)

            self.statusBar().showMessage("Calculation completed")

        except Exception as exc:
            QMessageBox.critical(self, "Calculation Error", f"Failed to calculate:\n{exc}")
            self.statusBar().showMessage("Calculation failed")

    def _update_profile_plot(self, grid):
        x, t = extract_centerline_profile(grid)
        self.profile_canvas.plot_profile(x, t)

    def _set_good_camera_view(self):
        self.plotter.view_isometric()
        self.plotter.camera.zoom(1.2)
        self.plotter.reset_camera()

    def _reset_camera(self):
        self.plotter.reset_camera()
        self.statusBar().showMessage("Camera reset")

    # ----------------------------
    # Save / Load
    # ----------------------------
    def save_parameters(self):
        params = self._get_parameters()
        params["mesh_density"] = self.mesh_combo.currentText()
        params["slice_display"] = self.slice_combo.currentText()

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Parameters",
            str(Path.cwd() / "mems_chip_params_v3.json"),
            "JSON Files (*.json)",
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(params, f, indent=4)

            self.current_project_path = file_path
            self.statusBar().showMessage(f"Saved parameters: {file_path}")

        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Failed to save parameters:\n{exc}")
            self.statusBar().showMessage("Save failed")

    def load_parameters(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Parameters",
            str(Path.cwd()),
            "JSON Files (*.json)",
        )

        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                params = json.load(f)

            self._set_parameters(params)
            self.current_project_path = file_path
            self._show_initial_geometry()
            self.statusBar().showMessage(f"Loaded parameters: {file_path}")

        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Failed to load parameters:\n{exc}")
            self.statusBar().showMessage("Load failed")

    # ----------------------------
    # Other actions
    # ----------------------------
    def reset_parameters(self):
        self.length_spin.setValue(1000.0)
        self.width_spin.setValue(1000.0)
        self.thickness_spin.setValue(50.0)
        self.k_spin.setValue(150.0)
        self.voltage_spin.setValue(5.0)
        self.boundary_temp_spin.setValue(300.0)
        self.mesh_combo.setCurrentText("Medium")
        self.slice_combo.setCurrentText("Mid-X Slice")

        self._show_initial_geometry()
        self.statusBar().showMessage("Parameters reset")

    def show_about_dialog(self):
        QMessageBox.information(
            self,
            "About",
            "MEMS Chip Thermal Demo - Version 3\n\n"
            "Features:\n"
            "- Geometry parameter input\n"
            "- Simplified thermal field calculation\n"
            "- 3D temperature visualization\n"
            "- Mid-section slice display\n"
            "- Centerline temperature profile\n"
            "- Mesh density switching\n"
            "- Save / load parameter sets\n"
            "- Ready for future multiphysics expansion",
        )

    def _update_result_text(self, params, stats, mode="initial"):
        mesh_name = self.mesh_combo.currentText()
        slice_name = self.slice_combo.currentText()

        if mode == "initial":
            text = (
                "[Model Preview]\n"
                "Initial chip geometry loaded.\n\n"
                "[Parameters]\n"
                f"Length L       : {params['L']:.3f} um\n"
                f"Width W        : {params['W']:.3f} um\n"
                f"Thickness T    : {params['T']:.3f} um\n"
                f"Thermal k      : {params['k']:.3f} W/mK\n"
                f"Voltage V      : {params['V']:.3f} V\n"
                f"Boundary Temp  : {params['T_boundary']:.3f} K\n"
                f"Mesh Density   : {mesh_name}\n"
                f"Slice Display  : {slice_name}\n\n"
                "[Preview Statistics]\n"
                f"Tmin           : {stats['Tmin']:.3f} K\n"
                f"Tmax           : {stats['Tmax']:.3f} K\n"
                f"Tavg           : {stats['Tavg']:.3f} K\n"
                f"Delta T        : {stats['dT']:.3f} K\n"
            )
        else:
            text = (
                "[Calculation Status]\n"
                "Calculation completed.\n\n"
                "[Input Parameters]\n"
                f"Length L       : {params['L']:.3f} um\n"
                f"Width W        : {params['W']:.3f} um\n"
                f"Thickness T    : {params['T']:.3f} um\n"
                f"Thermal k      : {params['k']:.3f} W/mK\n"
                f"Voltage V      : {params['V']:.3f} V\n"
                f"Boundary Temp  : {params['T_boundary']:.3f} K\n"
                f"Mesh Density   : {mesh_name}\n"
                f"Slice Display  : {slice_name}\n\n"
                "[Thermal Results]\n"
                f"Tmin           : {stats['Tmin']:.3f} K\n"
                f"Tmax           : {stats['Tmax']:.3f} K\n"
                f"Tavg           : {stats['Tavg']:.3f} K\n"
                f"Delta T        : {stats['dT']:.3f} K\n\n"
                "[Expected Trends]\n"
                "- Higher voltage -> higher temperature\n"
                "- Higher thermal conductivity -> lower temperature rise\n"
                "- Higher boundary temperature -> higher overall temperature\n"
                "- Finer mesh -> denser field sampling\n"
            )

        self.result_text.setPlainText(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())