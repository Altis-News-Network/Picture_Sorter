import sys
import os
import logging
import shutil
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QPushButton, QLabel, QFileDialog, QSlider, QProgressBar, 
                           QCheckBox, QMessageBox, QLineEdit, QGridLayout, QSplitter)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QFont, QPalette, QColor
import pytesseract
from PIL import Image

# Configure logging
logging.basicConfig(
    filename='text_image_sorter_gui.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ImageProcessorThread(QThread):
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    image_preview = pyqtSignal(str)
    processing_finished = pyqtSignal()
    
    def __init__(self, input_dir, output_dir, threshold, tesseract_path=None, preview=True):
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.threshold = threshold
        self.preview = preview
        self.is_running = True
        
        # Configure Tesseract path if provided
        if tesseract_path and os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            
    def run(self):
        try:
            # Get all supported image files
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif']
            image_files = []
            for file in os.listdir(self.input_dir):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_files.append(os.path.join(self.input_dir, file))
            
            total_files = len(image_files)
            if total_files == 0:
                self.status_updated.emit("No image files found in input directory")
                self.processing_finished.emit()
                return
                
            for i, image_path in enumerate(image_files):
                if not self.is_running:
                    self.status_updated.emit("Processing stopped")
                    break
                
                # Update progress
                progress = int((i / total_files) * 100)
                self.progress_updated.emit(progress)
                
                # Get filename for status updates
                filename = os.path.basename(image_path)
                self.status_updated.emit(f"Processing {filename} ({i+1}/{total_files})")
                
                # Send image for preview if enabled
                if self.preview:
                    self.image_preview.emit(image_path)
                
                # Detect text
                has_text = self.detect_text(image_path)
                
                if has_text:
                    # Move file to output directory if it contains text
                    output_path = os.path.join(self.output_dir, filename)
                    shutil.move(image_path, output_path)
                    self.status_updated.emit(f"Moved {filename} (contains text)")
                    logging.info(f"Moved {filename} to {output_path}")
            
            self.progress_updated.emit(100)
            self.status_updated.emit("Processing complete")
            self.processing_finished.emit()
            
        except Exception as e:
            self.status_updated.emit(f"Error: {str(e)}")
            logging.error(f"Error during processing: {str(e)}")
            self.processing_finished.emit()
    
    def detect_text(self, image_path):
        try:
            # Open image and convert to grayscale for better OCR
            img = Image.open(image_path).convert('L')
            
            # Use Tesseract to extract text with both German and English language support
            text = pytesseract.image_to_string(img, lang='deu+eng')
            
            # Check if meaningful text was found based on threshold
            # Count non-whitespace characters
            text_content = sum(1 for c in text if not c.isspace())
            image_size = img.width * img.height
            
            # Calculate text density ratio
            text_ratio = text_content / image_size if image_size > 0 else 0
            
            # Return True if text ratio is above threshold
            return text_ratio > self.threshold
            
        except Exception as e:
            logging.error(f"Error detecting text in {image_path}: {str(e)}")
            return False
    
    def stop(self):
        self.is_running = False

class TextImageSorterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.processor_thread = None
        
    def initUI(self):
        # Set window properties
        self.setWindowTitle('Text Image Sorter')
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: #2D2D30; color: #E0E0E0;")
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create directory selection section
        dir_layout = QGridLayout()
        
        # Input directory
        self.input_dir_label = QLabel("Input Directory:")
        self.input_dir_edit = QLineEdit()
        self.input_dir_edit.setReadOnly(True)
        self.input_dir_button = QPushButton("Browse...")
        self.input_dir_button.clicked.connect(self.select_input_dir)
        
        # Output directory
        self.output_dir_label = QLabel("Output Directory:")
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_button = QPushButton("Browse...")
        self.output_dir_button.clicked.connect(self.select_output_dir)
        
        # Tesseract path
        self.tesseract_label = QLabel("Tesseract Path (optional):")
        self.tesseract_edit = QLineEdit()
        self.tesseract_button = QPushButton("Browse...")
        self.tesseract_button.clicked.connect(self.select_tesseract)
        
        # Grid layout assignment
        dir_layout.addWidget(self.input_dir_label, 0, 0)
        dir_layout.addWidget(self.input_dir_edit, 0, 1)
        dir_layout.addWidget(self.input_dir_button, 0, 2)
        
        dir_layout.addWidget(self.output_dir_label, 1, 0)
        dir_layout.addWidget(self.output_dir_edit, 1, 1)
        dir_layout.addWidget(self.output_dir_button, 1, 2)
        
        dir_layout.addWidget(self.tesseract_label, 2, 0)
        dir_layout.addWidget(self.tesseract_edit, 2, 1)
        # Set default tesseract path to the subfolder
        tesseract_default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tesseract", "tesseract.exe")
        self.tesseract_edit.setText(tesseract_default_path)
        dir_layout.addWidget(self.tesseract_button, 2, 2)
        
        main_layout.addLayout(dir_layout)
        
        # Threshold controls section
        threshold_layout = QHBoxLayout()
        self.threshold_label = QLabel("Text Detection Threshold:")
        self.threshold_value_label = QLabel("0.020")
        self.threshold_value_label.setMinimumWidth(60)
        
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(1, 200)  # From 0.001 to 0.2
        self.threshold_slider.setValue(20)      # Default 0.02
        self.threshold_slider.valueChanged.connect(self.update_threshold_value)
        
        fine_tune_layout = QHBoxLayout()
        self.btn_minus_001 = QPushButton("-0.001")
        self.btn_minus_01 = QPushButton("-0.01")
        self.btn_plus_001 = QPushButton("+0.001")
        self.btn_plus_01 = QPushButton("+0.01")
        
        self.btn_minus_001.clicked.connect(lambda: self.fine_tune(-1))
        self.btn_minus_01.clicked.connect(lambda: self.fine_tune(-10))
        self.btn_plus_001.clicked.connect(lambda: self.fine_tune(1))
        self.btn_plus_01.clicked.connect(lambda: self.fine_tune(10))
        
        fine_tune_layout.addWidget(self.btn_minus_01)
        fine_tune_layout.addWidget(self.btn_minus_001)
        fine_tune_layout.addWidget(self.btn_plus_001)
        fine_tune_layout.addWidget(self.btn_plus_01)
        
        threshold_layout.addWidget(self.threshold_label)
        threshold_layout.addWidget(self.threshold_slider)
        threshold_layout.addWidget(self.threshold_value_label)
        
        main_layout.addLayout(threshold_layout)
        main_layout.addLayout(fine_tune_layout)
        
        # Preview checkbox
        self.preview_checkbox = QCheckBox("Preview images before moving")
        self.preview_checkbox.setChecked(True)
        main_layout.addWidget(self.preview_checkbox)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        # Image preview area (optional)
        self.image_preview = QLabel("Image Preview")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumHeight(200)
        self.image_preview.setStyleSheet("border: 1px solid #555;")
        main_layout.addWidget(self.image_preview)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_processing)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_processing)
        self.stop_button.setEnabled(False)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        
        main_layout.addLayout(button_layout)
        
        # Apply button styles
        self.apply_styles()
        
        # Show window
        self.show()
    
    def apply_styles(self):
        # Apply styles to buttons and controls
        button_style = """
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                padding: 5px;
                min-height: 25px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1C91EA;
            }
            QPushButton:pressed {
                background-color: #0053A6;
            }
            QPushButton:disabled {
                background-color: #666;
            }
        """
        
        slider_style = """
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #3D3D3D;
                margin: 2px 0;
                border-radius: 4px;
            }

            QSlider::handle:horizontal {
                background: #0078D7;
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 4px;
            }
            
            QSlider::handle:horizontal:hover {
                background: #1C91EA;
            }
        """
        
        for btn in self.findChildren(QPushButton):
            btn.setStyleSheet(button_style)
            btn.setMinimumWidth(80)
        
        self.threshold_slider.setStyleSheet(slider_style)
        
    def select_input_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Input Directory")
        if directory:
            self.input_dir_edit.setText(directory)
            
    def select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir_edit.setText(directory)
            
    def select_tesseract(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Tesseract Executable", 
                                            filter="Executable files (*.exe);;All files (*.*)")
        if file:
            self.tesseract_edit.setText(file)
            
    def update_threshold_value(self):
        threshold = self.threshold_slider.value() / 1000
        self.threshold_value_label.setText(f"{threshold:.3f}")
        
    def fine_tune(self, amount):
        current = self.threshold_slider.value()
        self.threshold_slider.setValue(current + amount)
        
    def start_processing(self):
        input_dir = self.input_dir_edit.text()
        output_dir = self.output_dir_edit.text()
        tesseract_path = self.tesseract_edit.text()
        threshold = float(self.threshold_value_label.text())
        preview_enabled = self.preview_checkbox.isChecked()
        
        if not input_dir or not os.path.isdir(input_dir):
            QMessageBox.warning(self, "Warning", "Please select a valid input directory.")
            return
            
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Warning", "Please select a valid output directory.")
            return
            
        # Update UI state
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Processing...")
        
        # Create and start the processor thread
        self.processor_thread = ImageProcessorThread(
            input_dir, output_dir, threshold, tesseract_path, preview_enabled
        )
        
        # Connect signals
        self.processor_thread.progress_updated.connect(self.progress_bar.setValue)
        self.processor_thread.status_updated.connect(self.status_label.setText)
        self.processor_thread.image_preview.connect(self.update_preview)
        self.processor_thread.processing_finished.connect(self.processing_complete)
        
        # Start processing
        self.processor_thread.start()
            
    def stop_processing(self):
        # Stop the processing thread
        if self.processor_thread and self.processor_thread.isRunning():
            self.processor_thread.stop()
            self.status_label.setText("Stopping processing...")
            # The thread will emit processing_finished when done
        
    def processing_complete(self):
        # Reset UI state
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
    def update_preview(self, image_path):
        try:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(self.image_preview.width(), 
                                      self.image_preview.height(),
                                      Qt.KeepAspectRatio,
                                      Qt.SmoothTransformation)
                self.image_preview.setPixmap(pixmap)
        except Exception as e:
            logging.error(f"Error updating preview: {str(e)}")

def apply_dark_theme(app):
    # Set application-wide dark theme
    app.setStyle("Fusion")
    
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(45, 45, 48))
    palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
    palette.setColor(QPalette.Base, QColor(37, 37, 38))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 48))
    palette.setColor(QPalette.ToolTipBase, QColor(37, 37, 38))
    palette.setColor(QPalette.ToolTipText, QColor(224, 224, 224))
    palette.setColor(QPalette.Text, QColor(224, 224, 224))
    palette.setColor(QPalette.Button, QColor(45, 45, 48))
    palette.setColor(QPalette.ButtonText, QColor(224, 224, 224))
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(0, 120, 215))
    palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.HighlightedText, Qt.white)
    
    app.setPalette(palette)

def main():
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    ex = TextImageSorterGUI()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()