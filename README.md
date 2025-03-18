# Kana's Text Image Sorter

Ein Programm zum Identifizieren und Sortieren von Bildern, die Text enthalten.

## Einrichtung

1. Führe `setup.bat` aus, um die virtuelle Umgebung einzurichten und alle Abhängigkeiten zu installieren
2. Starte die Anwendung mit `run.bat`

## Verwendung

1. Wähle einen Eingabeordner mit Bildern
2. Wähle einen Ausgabeordner für Bilder, die Text enthalten
3. Passe den Text-Erkennungsschwellenwert an (höherer Wert = mehr Text erforderlich)
4. Klicke auf "Start", um den Sortierprozess zu beginnen

## Funktionen

- Text-Erkennung in Bildern mit Tesseract OCR
- Numerische Fortschrittsanzeige (X/Y Bilder)
- Anpassbarer Erkennungsschwellenwert
- Optionale Vorschau der Bilder während des Sortierprozesses
- Dunkles Erscheinungsbild mit lilafarbenen Akzenten

## Anforderungen

- Python 3.6 oder höher
- Tesseract OCR (im Unterordner "tesseract" enthalten)
