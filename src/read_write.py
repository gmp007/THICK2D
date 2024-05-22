"""
  THICK2D -- Thickness Hierarchy Inference & Calculation Kit for 2D materials

  This program is free software; you can redistribute it and/or modify it under the
  terms of the GNU General Public License as published by the Free Software Foundation
  version 3 of the License.

  This program is distributed in the hope that it will be useful, but WITHOUT ANY
  WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
  PARTICULAR PURPOSE.  See the GNU General Public License for more details.
  
  Email: cekuma1@gmail.com

""" 
 
import sys
import os
import json
from ase.io import read, write
import shutil
import glob
from math import gcd
import re
import subprocess
from write_inputs import write_default_input, write_default_ystool_in, print_default_input_message_0, print_default_input_message_1, print_default_input_message_0



def append_data(filename,structure_name, thicknessval,matid=None):
    with open(filename, 'a') as file:
        matid_str = f", {matid}" if matid is not None else ""
        file.write(f"{structure_name}, {thicknessval} {matid_str}\n")
        
    
            
def read_options_from_input():

    cwd = os.getcwd()
    ystool_in_exists = os.path.exists(os.path.join(cwd, "thick2dtool.in"))
    run_mode_flag = (len(sys.argv) > 1 and sys.argv[1] == "-0")
    if run_mode_flag and not ystool_in_exists:
        write_default_ystool_in(cwd)
        print_default_input_message_0()
        sys.exit(0)

    # Generate auxiliary file
    aux_flag = (len(sys.argv) > 2 and sys.argv[1] == '-0' and sys.argv[2].lower() == '-aux') 
    aux_file_exists = os.path.exists(os.path.join(cwd, "throughput_thickness_calc.py"))

    if aux_flag and not aux_file_exists:
        write_highthroughput_script()
        print_fancy_message()
        sys.exit(0) 
    else:
        print("Usage: script.py -0 -aux") 
        sys.exit(0)      
        
    """
    Read the stress component options from the 'thick2dtool.in' file.
    ...
    rotation = on/off
    ...
    Returns:
    - Dictionary of the component settings.
    """
    options = {
        'code_type': 'VASP',
        'model_type': 'ml',
        'optimize': False,
        'use_ml_model': False,
        'nlayers': 1,
        'num_augmented_samples': 50,
        'add_thickness_data': False,
        'vdwgap': 3.5,
        'throughput': False,
        'custom_options': {},  # to store user-defined options
        'job_submit_command': None,
        'structure_file': None,
    }

    try:
        with open("thick2dtool.in", "r") as f:
            lines = f.readlines()
           # previous_line = None
            for line in lines:
                line = line.strip()
                if line.startswith("#") or not line:
                    #previous_line = line.strip()
                    continue
                key, value = line.strip().split('=', 1)
                key = key.strip()
                value = value.strip()

                if key in ["structure_file", "job_submit_command"]:
                    options[key] = value
                elif key == "components":
                    options[key] = value.split()
                elif key in ["code_type","model_type"]:
                    options[key] = value.upper()
                elif key in ["optimize","use_ml_model", "throughput","add_thickness_data"]:
                    options[key] = value.lower() in ['true', 'yes', '1','on']
                elif key in options:
                    if key in ['nlayers','vdwgap','num_augmented_samples']:
                        options[key] = float(value)
                    else:
                        options[key] = value.lower() == 'on'
                else:
                    options['custom_options'][key] = value

        if options.get('job_submit_command'):
            os.environ["ASE_VASP_COMMAND"] = options['job_submit_command']

    except FileNotFoundError:
        print("'thick2dtool.in' file not found. Using default settings.")
        
    code_type = options.get("code_type")
    run_mode_flag = (len(sys.argv) > 1 and sys.argv[1] == "-0") #and 'dimensional' in options
    if run_mode_flag and ystool_in_exists:
        write_default_input(cwd,code_type)
        print_default_input_message_1()
        sys.exit(0)
        
    return options


def load_structure(options):
    options = read_options_from_input()
    filename = options.get('structure_file', None)
    
    if filename:
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Provided file {filename} is not found.")
        return read(filename)

    vasp_files = glob.glob("*.vasp")
    cif_files = glob.glob("*.cif")

    if len(vasp_files) > 1 or len(cif_files) > 1:
        raise RuntimeError("Multiple VASP or CIF files detected. Please have only one of each.")

    if vasp_files and cif_files:
        vasp_base = os.path.splitext(vasp_files[0])[0]
        cif_base = os.path.splitext(cif_files[0])[0]

        if vasp_base == cif_base:
            raise RuntimeError("Both VASP and CIF files are present with the same basename. Ambiguous input.")

    if vasp_files:
        return read(vasp_files[0])
    elif cif_files:
        cif_filename = cif_files[0]
        vasp_equivalent = os.path.splitext(cif_filename)[0] + ".vasp"
        cif_orig = os.path.splitext(cif_filename)[0] + "_orig.cif"
        
        convert_cif_to_vasp(cif_filename, vasp_equivalent)  
        os.rename(cif_filename, cif_orig)
        
        return read(vasp_equivalent)
    else:
        raise FileNotFoundError("Neither VASP nor CIF file is found.")



def convert_cif_to_vasp(cif_file, vasp_file):
    """
    Convert a CIF file to VASP format using ASE.
    
    Args:
    - cif_file (str): Path to the input CIF file.
    - vasp_file (str): Path to the output VASP file.
    """
    
    # Read the structure from the CIF file
    atoms = read(cif_file)

    # Write the structure in VASP format
    write(vasp_file, atoms, format='vasp', direct=True)



def write_incar(step, cwd, output_dir=None):
    infile = cwd + '/INCARs'
    outfile = 'INCAR' if output_dir is None else os.path.join(output_dir, 'INCAR')
    tag = '# Step:'
    
    step_dict = {
        'opt': 'DFT Optimization'
    }

    is_write = False

    #print(f"Looking for: {step_dict[step]}")  # Debug print
    with open(infile, 'r') as infile, open(outfile, 'w') as ofile:
        for line in infile:
            if tag in line:
                # print(f"Found step line: {line.strip()}")  # Debug print
                is_write = step_dict[step] in line
                # print(f"is_write set to: {is_write}")  # Debug print

            if is_write:
                # print(f"Writing line: {line.strip()}")  # Debug print
                ofile.write(line)
                
                

def modify_incar_and_restart():
    # Decrease EDIFF value in INCAR file
    with open("INCAR", "r") as file:
        lines = file.readlines()

    with open("INCAR", "w") as file:
        for line in lines:
            if line.startswith("EDIFF"):
                # Assuming the line is something like "EDIFF = 1E-4"
                parts = line.split("=")
                ediff_value = float(parts[1].strip())
                new_ediff = ediff_value / 10  # Decrease EDIFF by an order of magnitude
                line = f"EDIFF = {new_ediff}\n"
            file.write(line)

    # Copy CONTCAR to POSCAR for restart
    if os.path.exists("CONTCAR"):
        shutil.copyfile("CONTCAR", "POSCAR")
        
        
        
def read_incars(step, fileName="INCARs", directory=None):
    """
    Reads settings for the specified step and section from the INCARs file.

    Parameters:
    - step: The step corresponding to a section in the INCARs.
    - fileName: The name of the INCARs file. Defaults to "INCARs".
    - directory: The directory where the INCARs file is located.

    Returns:
    - Dictionary containing the settings for the specified step and section.
    """
    step_dict = {
    'opt': 'DFT Optimization',
    }  
    
    section_name = step_dict[step] 
    
    if directory:
        fileName = os.path.join(directory, fileName)
    
    with open(fileName, "r") as f:
        lines = f.readlines()

    in_section = False
    settings = {}

    for line in lines:
        line = line.strip()

        if line.startswith("#"):
            found_section = line[2:].strip()
            
            if section_name in found_section:
                in_section = True
                continue

        if in_section:
            if "=" in line:
                
                key, value = [item.strip() for item in line.split("=")]
                #print(f"Found step line: {key}, {value}")  # Debug print
                value = value.strip().lower()
                if value in [".true.", "true"]:
                    value = True
                elif value in [".false.", "false"]:
                    value = False
                else:
                    try:
                        value = int(value)
                    except ValueError:
                        try:
                            value = float(value)
                        except ValueError:
                            pass
                settings[key.lower()] = value

    return settings
    

def read_and_write_kpoints(step=None, calculation_type=None, fileName="KPOINTS", directory=None, outputDirectory=None):
    step_dict = {
        'static': 'Step: Static Calculation',
        'dynamic': 'Step: Dynamical Calculation'
    }
    
    section_name = step_dict.get(step)
    
    if directory:
        fileName = os.path.join(directory, fileName)
    
    with open(fileName, 'r') as f:
        lines = f.readlines()
    
    in_section = False
    kpoints_data = []
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("#"):
            found_section = line[2:].strip()
            in_section = found_section == section_name
        elif in_section:
            kpoints_data.append(line)
    
    # If a specific output directory is given, create the KPOINTS file there
    if outputDirectory:
        output_file_path = os.path.join(outputDirectory, "KPOINTS")
        if not os.path.exists(outputDirectory):
            os.makedirs(outputDirectory)
    else:
        output_file_path = "KPOINTS"
    
    with open(output_file_path, 'w') as f:
        f.write("\n".join(kpoints_data))
    
    kpoints = list(map(int, kpoints_data[2].split()))
    
    return kpoints, output_file_path
              

def merge_qe_parameters(existing_params, new_step_data):
    new_input_data = new_step_data.get('input_data', {})
    new_pseudopotentials = new_step_data.get('pseudopotentials', None)
    new_kpts = new_step_data.get('kpts', None)

    original_pseudo_dir = existing_params.get('input_data', {}).get('control', {}).get('pseudo_dir', None)

    for key in ['control', 'system', 'electrons', 'cell', 'ions']:
        if key in new_input_data:
            if key in existing_params.get('input_data', {}):
                if key == 'control':
                    temp_control = new_input_data['control'].copy()
                    temp_control.pop('pseudo_dir', None) 
                    existing_params['input_data']['control'].update(temp_control)
                else:
                    existing_params['input_data'][key].update(new_input_data[key])
            else:
                existing_params['input_data'][key] = new_input_data[key]

    if original_pseudo_dir is not None:
        existing_params['input_data']['control']['pseudo_dir'] = original_pseudo_dir

    if new_pseudopotentials is not None:
        existing_params['pseudopotentials'] = new_pseudopotentials
    if new_kpts is not None:
        existing_params['kpts'] = new_kpts

    return existing_params


#def escape_special_characters(path):
#    # List of special characters you want to escape
#    special_chars = ['(', ')', ' ', '&', '`', '"', '\'']
#    for char in special_chars:
#        path = path.replace(char, f"\\{char}")
#    return path



def process_cif_files(control_file_path, cif_dir):
    """
    Processes CIF files by updating the control file and running thick2d for each CIF file.

    Args:
    control_file_path (str): Path to the control file (thick2dtool.in).
    cif_dir (str): Directory containing CIF files.
    """
    # Backup the original control file content
    with open(control_file_path, 'r') as file:
        original_content = file.read()

    # Iterate over CIF files
    for cif_file in os.listdir(cif_dir):
        if cif_file.endswith('.cif'):
            with open(control_file_path, 'r') as file:
                control_content = file.readlines()


            structure_file_line = f"structure_file = {cif_file}\n"
            structure_line_exists = any(line.startswith('structure_file') for line in control_content)
            if structure_line_exists:
                modified_content = [line if not line.startswith('structure_file') else structure_file_line for line in control_content]
            else:
                modified_content = control_content + [structure_file_line]

            with open(control_file_path, 'w') as file:
                file.writelines(modified_content)

            subprocess.run(['thick2d', control_file_path], cwd=cif_dir)

    with open(control_file_path, 'w') as file:
        file.write(original_content)
              

##########
aux_file = '''import os
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
'''

def write_highthroughput_script():
    with open('throughput_thickness_calc.py', 'w') as file:
        file.write(aux_file)


def print_fancy_message():
    message = (
        "High-throughput script has been written to throughput_thickness_calc.py\n"
        "Follow the instructions in the code to\n"
        "perform high-throughput prediction of thickness of 2D materials"
    )
    border = "*" * (len(max(message.split('\n'), key=len)) + 4)
    print(f"\n{border}")
    for line in message.split('\n'):
        print(f"* {line.center(len(border) - 4)} *")
    print(border)
    
                
if __name__ == '__main__':
    import os
    cwd = os.getcwd()
