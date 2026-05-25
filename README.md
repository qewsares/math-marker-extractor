# Math Marker Extractor

Извлечение маркеров "тогда и только тогда" и "критерий" из PDF-статей с распознаванием формул.

## Установка и запуск

### Установка Miniconda

Скачать Miniconda с [официального сайта](https://www.anaconda.com/download/success).

```bash
# Перейдите в папку с проектом
cd путь_к_папке

# Создайте виртуальное окружение
conda create -n НАЗВАНИЕ_ОКРУЖЕНИЯ python=3.10 -y

# Активируйте его
conda activate НАЗВАНИЕ_ОКРУЖЕНИЯ

# Установите  зависимости
pip install pypdf PyMuPDF pillow pix2text natasha
# Запустите скрипт
python extractor.py
```
## Работа в Visual Studio Code
Откройте папку проекта в VS Code

Нажмите Ctrl + Shift + P → выбери Python: Select Interpreter

Выберите интерпретатор из созданного окружения (путь типа C:\Users\твое_имя\miniconda3\envs\НАЗВАНИЕ_ОКРУЖЕНИЯ\python.exe)

Откройте новый терминал (Ctrl + ~) — окружение активируется само

Запускайте скрипт кнопкой или командой python final.py

Если терминал не активирует окружение — напишите вручную: conda activate НАЗВАНИЕ_ОКРУЖЕНИЯ

**Самый надежный вариант работать напрямую из Anaconda Prompt!**
# Структура проекта
**math-marker-extractor**

[pdfs](pdfs/) - Хранятся все PDF

[result.json](result.json) — JSON с найденными маркерами

[final.py](final.py) - Сам скрипт

[Отчет.docx](Отчет.docx) - Отчет о проделанной работе
