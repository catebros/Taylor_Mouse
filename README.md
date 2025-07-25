# Taylor_Mouse

A Python tool for efficient image cropping and processing.

Python = 3.8.10

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/catebros/Taylor_Mouse.git
   ```
2. Navigate to the project directory:
   ```bash
   cd Taylor_Mouse
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
4. Activate the virtual environment:
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS and Linux:
     ```bash
     source venv/bin/activate
     ```
5. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage
```bash
streamlit run Taylor_Mouse.py
```

## Troubleshooting

### "Python not found" error
Make sure Python 3.8.10 is installed and added to your system PATH.

### Cannot activate virtual environment
- On Windows, you may need to run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- Verify the virtual environment was created correctly

### Dependency installation issues
If you encounter errors installing dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir
```