\# Environment Setup and Installation Guide



This document provides instructions for initializing the python runtime environment and installing all dependencies required to execute the \*\*TRACEBIND-W11\*\* simulation sweeps and figure-generation scripts.



\## Prerequisite

\* \*\*Python\*\*: `3.11.x` or higher (tested on Python 3.11.9)



\## 1. Virtual Environment Initialization



From the project root directory, create and activate an isolated Python virtual environment:



\### On Windows (Command Prompt)

```cmd

python -m venv venv

call venv\\Scripts\\activate



On Linux / macOS



python -m venv venv

source venv/bin/activate



\## 2. Install Package Dependencies

With the virtual environment activated, install the locked project requirements using pip:



pip install --upgrade pip

pip install -r requirements.txt



\## 3. Verifying the Installation

To verify that the plotting engine and numerical libraries are correctly configured, execute the visual compilation scripts:



python scripts/generate\_figure\_01.py

python scripts/generate\_figure\_02.py



\---





