#!/bin/bash

echo "==================================================="
echo "Setting up Solar PV App environment on Mac/Linux..."
echo "==================================================="
echo ""

# Check if python3 is installed
if ! command -v python3 &> /dev/null
then
    echo "Python 3 could not be found. Please install Python 3.10+ and try again."
    exit
fi

echo "Creating virtual environment (.venv)..."
python3 -m venv .venv

echo ""
echo "Activating virtual environment..."
source .venv/bin/activate

echo ""
echo "Upgrading pip..."
python3 -m pip install --upgrade pip

echo ""
echo "Installing requirements..."
pip install -r requirements.txt

echo ""
echo "==================================================="
echo "Setup complete!"
echo "To run the app or scripts, always activate the environment first by running:"
echo "source .venv/bin/activate"
echo "==================================================="
