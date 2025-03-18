import sys
import os
import logging
import shutil
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QPushButton, QLabel, QFileDialog, QSlider, QProgressBar, 
                           QCheckBox, QMessageBox, QLineEdit, QGridLayout, QSplitter,
                           QSpinBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex
from PyQt5.QtGui import QPixmap, QFont, QPalette, QColor
import pytesseract
from PIL import Image
import concurrent.futures
import multiprocessing

# Configure logging - start with disabled state
logging.basicConfig(
    filename='text_image_sorter_gui.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Create a dummy logger that does nothing when logging is disabled
class NullHandler(logging.Handler):
    def emit(self, record):
        pass

# Global logging state
logging_enabled = False  # Standardmäßig deaktiviert

def toggle_logging(enabled):
    global logging_enabled
    logging_enabled = enabled
    
    # Remove all handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    if enabled:
        # Add file handler when enabled
        file_handler = logging.FileHandler('text_image_sorter_gui.log')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.root.addHandler(file_handler)
    else:
        # Add null handler when disabled
        logging.root.addHandler(NullHandler())

# Custom logger function that respects the enabled state
def log_info(message):
    if logging_enabled:
        logging.info(message)

def log_error(message):
    if logging_enabled:
        logging.error(message)

# Initialize logging state
toggle_logging(logging_enabled)

class ImageProcessorThread(QThread):
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    image_preview = pyqtSignal(str)
    processing_finished = pyqtSignal()
    progress_count_updated = pyqtSignal(int, int)  # Signal für aktuelle/gesamte Bildanzahl
    
    def __init__(self, input_dir, output_dir, threshold, tesseract_path=None, preview=True, parallel=True, workers=2):
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.threshold = threshold
        self.preview = preview
        self.is_running = True
        self.parallel = parallel
        self.workers = workers if parallel else 1
        self.mutex = QMutex()  # Für thread-sichere Operationen
        self.processed_count = 0
        
        # Configure Tesseract path if provided
        if tesseract_path and os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            
    def process_image(self, image_data):
        """Prozessiert ein einzelnes Bild in einem Worker-Thread"""
        if not self.is_running:
            return None, False
            
        image_path, index, total_files = image_data
        
        # Get filename for status updates
        filename = os.path.basename(image_path)
        self.status_updated.emit(f"Processing {filename}")
        
        # Send image for preview if enabled
        if self.preview:
            self.image_preview.emit(image_path)
        
        # Detect text
        try:
            has_text = self.detect_text(image_path)
            
            if has_text:
                # Thread-sicheres Verschieben der Datei
                self.mutex.lock()
                try:
                    output_path = os.path.join(self.output_dir, filename)
                    shutil.move(image_path, output_path)
                    log_info(f"Moved {filename} to {output_path}")
                    self.status_updated.emit(f"Moved {filename} (contains text)")
                finally:
                    self.mutex.unlock()
        except Exception as e:
            log_error(f"Error processing image {filename}: {str(e)}")
            has_text = False
            
        # Thread-sichere Fortschrittsaktualisierung
        self.mutex.lock()
        try:
            self.processed_count += 1
            progress = int((self.processed_count / total_files) * 100)
            self.progress_updated.emit(progress)
            self.progress_count_updated.emit(self.processed_count, total_files)
        finally:
            self.mutex.unlock()
            
        return image_path, has_text
            
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
            
            # Reset counter    
            self.processed_count = 0
            
            # Bereite Daten für parallele Verarbeitung vor
            image_data = [(image_path, i, total_files) for i, image_path in enumerate(image_files)]
            
            if self.parallel and total_files > 1:
                # Parallele Verarbeitung
                log_info(f"Starting parallel processing with {self.workers} workers")
                self.status_updated.emit(f"Processing with {self.workers} parallel workers...")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
                    futures = [executor.submit(self.process_image, data) for data in image_data]
                    
                    # Überwachung der Ausführung für vorzeitigen Abbruch
                    while futures and self.is_running:
                        # Warte auf den nächsten abgeschlossenen Thread
                        done, futures = concurrent.futures.wait(
                            futures, timeout=0.5, 
                            return_when=concurrent.futures.FIRST_COMPLETED
                        )
                        
                        if not self.is_running:
                            executor.shutdown(wait=False)
                            self.status_updated.emit("Processing stopped")
                            break
            else:
                # Sequentielle Verarbeitung
                log_info("Starting sequential processing")
                for data in image_data:
                    if not self.is_running:
                        self.status_updated.emit("Processing stopped")
                        break
                    self.process_image(data)
            
            # Nur 100% anzeigen, wenn alle Dateien verarbeitet wurden
            if self.is_running:
                self.progress_updated.emit(100)
                self.progress_count_updated.emit(total_files, total_files)
                self.status_updated.emit("Processing complete")
            
            self.processing_finished.emit()
            
        except Exception as e:
            self.status_updated.emit(f"Error: {str(e)}")
            log_error(f"Error during processing: {str(e)}")
            self.processing_finished.emit()
    
    def detect_text(self, image_path):
        try:
            # Open image and convert to grayscale for better OCR
            img = Image.open(image_path).convert('L')
            
            # Log attempt to detect text
            log_info(f"Attempting text detection on {image_path}")
            
            # Configure Tesseract for better text detection
            # Use PSM 6 (Assume a single uniform block of text) for better results with small text
            config = '--psm 6 --oem 3 -c tessedit_do_invert=0 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?@#$%&*()-+="'
            
            # Use Tesseract to extract text
            text = pytesseract.image_to_string(img, config=config)
            
            # Check if meaningful text was found based on threshold
            # Count non-whitespace characters
            text_content = sum(1 for c in text if not c.isspace())
            image_size = img.width * img.height
            
            # Calculate text density ratio
            text_ratio = text_content / image_size if image_size > 0 else 0
            
            # Log detection results
            log_info(f"Text detection results for {os.path.basename(image_path)}: chars={text_content}, ratio={text_ratio}, threshold={self.threshold}")
            log_info(f"Sample text found: {text[:100].strip()}")
            
            # Return True if text ratio is above threshold
            return text_ratio > self.threshold
            
        except Exception as e:
            log_error(f"Error detecting text in {image_path}: {str(e)}")
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
        self.setWindowTitle('Kana\'s Text Image Sorter')
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
        self.threshold_value_label = QLabel("0.00025")
        self.threshold_value_label.setMinimumWidth(60)
        
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(1, 100)  # From 0.00001 to 0.001
        self.threshold_slider.setValue(25)      # Default 0.00025
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
        
        # Parallel processing controls
        parallel_layout = QHBoxLayout()
        
        self.parallel_checkbox = QCheckBox("Enable Parallel Processing")
        self.parallel_checkbox.setChecked(True)  # Standardmäßig aktiviert
        self.parallel_checkbox.stateChanged.connect(self.toggle_worker_controls)
        
        worker_layout = QHBoxLayout()
        self.worker_label = QLabel("Worker Threads:")
        
        self.worker_spinner = QSpinBox()
        # Setze Worker-Anzahl auf CPU-Kerne (max 8, min 2)
        cpu_count = max(2, min(multiprocessing.cpu_count(), 8))
        self.worker_spinner.setMinimum(1)
        self.worker_spinner.setMaximum(cpu_count * 2)  # Erlaube bis zu doppelte Anzahl der CPU-Kerne
        self.worker_spinner.setValue(cpu_count)
        self.worker_spinner.setEnabled(True)
        self.worker_spinner.setToolTip(f"Recommended: {cpu_count} (number of CPU cores)")
        
        worker_layout.addWidget(self.worker_label)
        worker_layout.addWidget(self.worker_spinner)
        
        parallel_layout.addWidget(self.parallel_checkbox)
        parallel_layout.addStretch()
        parallel_layout.addLayout(worker_layout)
        
        main_layout.addLayout(parallel_layout)
        
        # Preview and logging checkboxes
        checkbox_layout = QHBoxLayout()
        
        self.preview_checkbox = QCheckBox("Preview images before moving")
        self.preview_checkbox.setChecked(False)  # Standardmäßig deaktiviert
        
        self.logging_checkbox = QCheckBox("Enable logging")
        self.logging_checkbox.setChecked(False)  # Standardmäßig deaktiviert
        self.logging_checkbox.clicked.connect(self.toggle_logging)
        
        checkbox_layout.addWidget(self.preview_checkbox)
        checkbox_layout.addStretch()
        checkbox_layout.addWidget(self.logging_checkbox)
        
        main_layout.addLayout(checkbox_layout)
        
        # Progress bar and counter
        progress_layout = QHBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        self.progress_counter = QLabel("0/0")
        self.progress_counter.setMinimumWidth(80)
        self.progress_counter.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_counter)
        
        main_layout.addLayout(progress_layout)
        
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
        purple_accent = "#691868"  # Neue Lila Akzentfarbe
        
        button_style = f"""
            QPushButton {{
                background-color: {purple_accent};
                color: white;
                border: none;
                padding: 5px;
                min-height: 25px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: #8A2089;
            }}
            QPushButton:pressed {{
                background-color: #4A1248;
            }}
            QPushButton:disabled {{
                background-color: #666;
            }}
        """
        
        slider_style = f"""
            QSlider::groove:horizontal {{
                border: 1px solid #999999;
                height: 8px;
                background: #3D3D3D;
                margin: 2px 0;
                border-radius: 4px;
            }}

            QSlider::handle:horizontal {{
                background: {purple_accent};
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 4px;
            }}
            
            QSlider::handle:horizontal:hover {{
                background: #8A2089;
            }}
        """
        
        progress_style = f"""
            QProgressBar {{
                border: 1px solid #666;
                border-radius: 3px;
                text-align: center;
                background-color: #2D2D30;
            }}
            
            QProgressBar::chunk {{
                background-color: {purple_accent};
                width: 1px;
            }}
        """
        
        for btn in self.findChildren(QPushButton):
            btn.setStyleSheet(button_style)
            btn.setMinimumWidth(80)
        
        self.threshold_slider.setStyleSheet(slider_style)
        self.progress_bar.setStyleSheet(progress_style)
        
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
        threshold = self.threshold_slider.value() / 100000  # Much lower threshold range
        self.threshold_value_label.setText(f"{threshold:.5f}")
        
    def fine_tune(self, amount):
        current = self.threshold_slider.value()
        self.threshold_slider.setValue(current + amount)
        
    def toggle_worker_controls(self, state):
        """Aktiviere/Deaktiviere Worker-Controls basierend auf Checkbox-Zustand"""
        self.worker_spinner.setEnabled(state == Qt.Checked)
        self.worker_label.setEnabled(state == Qt.Checked)
    
    def start_processing(self):
        input_dir = self.input_dir_edit.text()
        output_dir = self.output_dir_edit.text()
        tesseract_path = self.tesseract_edit.text()
        threshold = float(self.threshold_value_label.text())
        preview_enabled = self.preview_checkbox.isChecked()
        parallel_enabled = self.parallel_checkbox.isChecked()
        worker_count = self.worker_spinner.value() if parallel_enabled else 1
        
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
            input_dir, output_dir, threshold, tesseract_path, preview_enabled,
            parallel_enabled, worker_count
        )
        
        # Connect signals
        self.processor_thread.progress_updated.connect(self.progress_bar.setValue)
        self.processor_thread.status_updated.connect(self.status_label.setText)
        self.processor_thread.image_preview.connect(self.update_preview)
        self.processor_thread.processing_finished.connect(self.processing_complete)
        self.processor_thread.progress_count_updated.connect(self.update_progress_counter)
        
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
        
    def toggle_logging(self, checked):
        toggle_logging(checked)
        
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
            log_error(f"Error updating preview: {str(e)}")
    
    def update_progress_counter(self, current, total):
        self.progress_counter.setText(f"{current}/{total}")

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