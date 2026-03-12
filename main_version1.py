
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pyvistaqt import QtInteractor

from solver import solve_thermal_field


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MEMS Beam Thermal Demo")
        self.resize(1400, 800)

        self._build_ui()
        self._show_initial_geometry()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 左侧参数面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)

        geom_group = QGroupBox("Geometry Parameters")
        geom_form = QFormLayout()

        self.length_spin = self._make_spinbox(200.0, 10.0, 5000.0, 1.0)
        self.width_spin = self._make_spinbox(20.0, 1.0, 1000.0, 1.0)
        self.thickness_spin = self._make_spinbox(10.0, 1.0, 500.0, 1.0)

        geom_form.addRow("Length L (um)", self.length_spin)
        geom_form.addRow("Width W (um)", self.width_spin)
        geom_form.addRow("Thickness T (um)", self.thickness_spin)
        geom_group.setLayout(geom_form)

        material_group = QGroupBox("Material Parameters")
        material_form = QFormLayout()

        self.k_spin = self._make_spinbox(150.0, 0.1, 10000.0, 1.0)
        material_form.addRow("Thermal k (W/mK)", self.k_spin)
        material_group.setLayout(material_form)

        drive_group = QGroupBox("Drive & Boundary")
        drive_form = QFormLayout()

        self.voltage_spin = self._make_spinbox(5.0, 0.0, 100.0, 0.1)
        self.boundary_temp_spin = self._make_spinbox(300.0, 0.0, 2000.0, 1.0)

        drive_form.addRow("Voltage V (V)", self.voltage_spin)
        drive_form.addRow("Boundary Temp (K)", self.boundary_temp_spin)
        drive_group.setLayout(drive_form)

        button_group = QGroupBox("Actions")
        button_layout = QVBoxLayout()

        self.calc_button = QPushButton("Calculate")
        self.reset_button = QPushButton("Reset")
        self.calc_button.clicked.connect(self.calculate_and_render)
        self.reset_button.clicked.connect(self.reset_parameters)

        button_layout.addWidget(self.calc_button)
        button_layout.addWidget(self.reset_button)
        button_group.setLayout(button_layout)

        left_layout.addWidget(geom_group)
        left_layout.addWidget(material_group)
        left_layout.addWidget(drive_group)
        left_layout.addWidget(button_group)
        left_layout.addStretch()

        # 中间3D视图
        self.plotter = QtInteractor(self)
        self.plotter.set_background("white")

        # 右侧结果面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        result_title = QLabel("Results")
        result_title.setAlignment(Qt.AlignCenter)
        result_title.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)

        tip_label = QLabel(
            "Usage:\n"
            "1. Modify parameters on the left\n"
            "2. Click Calculate\n"
            "3. Rotate / zoom the 3D model with mouse"
        )
        tip_label.setWordWrap(True)

        right_layout.addWidget(result_title)
        right_layout.addWidget(self.result_text)
        right_layout.addWidget(tip_label)

        # 设置左右比例
        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(self.plotter.interactor, 6)
        main_layout.addWidget(right_panel, 2)

    def _make_spinbox(self, value, min_val, max_val, step):
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(value)
        spin.setSingleStep(step)
        spin.setDecimals(3)
        return spin

    def _get_parameters(self):
        return {
            "L": self.length_spin.value(),
            "W": self.width_spin.value(),
            "T": self.thickness_spin.value(),
            "k": self.k_spin.value(),
            "V": self.voltage_spin.value(),
            "T_boundary": self.boundary_temp_spin.value(),
        }

    def _show_initial_geometry(self):
        params = self._get_parameters()
        self.plotter.clear()

        try:
            grid, stats = solve_thermal_field(**params)
            self.plotter.add_mesh(
                grid.outline(),
                color="black",
                line_width=2,
            )
            self.plotter.add_text("Initial MEMS Beam Geometry", font_size=12)
            self.plotter.reset_camera()
            self._update_result_text(params, stats, initial=True)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to initialize geometry:\n{exc}")

    def calculate_and_render(self):
        params = self._get_parameters()

        try:
            grid, stats = solve_thermal_field(**params)

            self.plotter.clear()
            self.plotter.add_mesh(
                grid,
                scalars="Temperature",
                show_edges=False,
                scalar_bar_args={"title": "Temperature (K)"},
                cmap="jet",
            )
            self.plotter.add_axes()
            self.plotter.add_text("MEMS Beam Temperature Field", font_size=12)
            self.plotter.reset_camera()

            self._update_result_text(params, stats, initial=False)

        except Exception as exc:
            QMessageBox.critical(self, "Calculation Error", f"Failed to calculate:\n{exc}")

    def reset_parameters(self):
        self.length_spin.setValue(200.0)
        self.width_spin.setValue(20.0)
        self.thickness_spin.setValue(10.0)
        self.k_spin.setValue(150.0)
        self.voltage_spin.setValue(5.0)
        self.boundary_temp_spin.setValue(300.0)

        self._show_initial_geometry()

    def _update_result_text(self, params, stats, initial=False):
        if initial:
            text = (
                "Initial model loaded.\n\n"
                "Current Parameters:\n"
                f"- Length L: {params['L']:.3f} um\n"
                f"- Width W: {params['W']:.3f} um\n"
                f"- Thickness T: {params['T']:.3f} um\n"
                f"- Thermal k: {params['k']:.3f} W/mK\n"
                f"- Voltage V: {params['V']:.3f} V\n"
                f"- Boundary Temp: {params['T_boundary']:.3f} K\n\n"
                "Preview Statistics:\n"
                f"- Tmin: {stats['Tmin']:.3f} K\n"
                f"- Tmax: {stats['Tmax']:.3f} K\n"
                f"- Tavg: {stats['Tavg']:.3f} K\n"
            )
        else:
            text = (
                "Calculation completed.\n\n"
                "Input Parameters:\n"
                f"- Length L: {params['L']:.3f} um\n"
                f"- Width W: {params['W']:.3f} um\n"
                f"- Thickness T: {params['T']:.3f} um\n"
                f"- Thermal k: {params['k']:.3f} W/mK\n"
                f"- Voltage V: {params['V']:.3f} V\n"
                f"- Boundary Temp: {params['T_boundary']:.3f} K\n\n"
                "Thermal Results:\n"
                f"- Tmin: {stats['Tmin']:.3f} K\n"
                f"- Tmax: {stats['Tmax']:.3f} K\n"
                f"- Tavg: {stats['Tavg']:.3f} K\n\n"
                "Expected trends:\n"
                "- Higher voltage -> higher temperature\n"
                "- Higher thermal conductivity -> lower temperature rise\n"
                "- Higher boundary temperature -> higher overall field\n"
            )

        self.result_text.setPlainText(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())