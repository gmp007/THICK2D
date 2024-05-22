import os
import subprocess
import sys

# Check for correct number of command line arguments
if len(sys.argv) != 3:
    print("Incorrect number of arguments provided.")
    print("Usage: python script.py <cif_directory> <control_file_directory>")
    print("\n<cif_directory> should be the path to the directory containing your CIF files.")
    print("<control_file_directory> should be the path to the directory where your 'thick2dtool.in' control file is located.")
    print("\nExample: python script.py /path/to/cif /path/to/control")
    sys.exit(1)

# Directory containing CIF files
cif_dir = sys.argv[1]

# Path to the directory where the control file is located
control_file_dir = sys.argv[2]
control_file_path = os.path.join(control_file_dir, 'thick2dtool.in')

# Check if CIF directory exists
if not os.path.isdir(cif_dir):
    print(f"The specified CIF directory does not exist: {cif_dir}")
    sys.exit(1)

# Check if control file exists
if not os.path.isfile(control_file_path):
    print(f"The specified control file does not exist: {control_file_path}")
    sys.exit(1)

# Backup the original control file content
with open(control_file_path, 'r') as file:
    original_content = file.read()

# Iterate over CIF files
for cif_file in os.listdir(cif_dir):
    if cif_file.endswith('.cif'):
        # Re-read the control file to reset any previous modification
        with open(control_file_path, 'r') as file:
            control_content = file.readlines()

        # Construct the line to insert with the CIF file name
        structure_file_line = f"structure_file = {cif_file}\n"
        # Find if structure_file line exists, if so replace it, if not append
        structure_line_exists = any(line.startswith('structure_file') for line in control_content)
        if structure_line_exists:
            modified_content = [line if not line.startswith('structure_file') else structure_file_line for line in control_content]
        else:
            modified_content = control_content + [structure_file_line]

        # Overwrite the control file with the modified content
        with open(control_file_path, 'w') as file:
            file.writelines(modified_content)

        # Run thick2d with the updated control file
        subprocess.run(['thick2d', control_file_path], cwd=cif_dir)

# Optionally, restore the original content of the control file after all operations
with open(control_file_path, 'w') as file:
    file.write(original_content)


# Usage: python file.py cif_dir thick2dtool_dir
