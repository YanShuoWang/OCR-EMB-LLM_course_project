import subprocess
import sys
import os

def main():
    # Check if app.py exists
    if not os.path.exists("app.py"):
        print("Error: app.py not found in current directory")
        sys.exit(1)
    
    # Run streamlit command
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running Streamlit: {e}")
    except KeyboardInterrupt:
        print("\nStreamlit server stopped by user")

if __name__ == "__main__":
    main()