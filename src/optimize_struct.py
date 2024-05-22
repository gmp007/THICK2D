"""
  SMATool -- Automated toolkit for computing zero and finite-temperature strength of materials

  This program is free software; you can redistribute it and/or modify it under the
  terms of the GNU General Public License as published by the Free Software Foundation
  version 3 of the License.

  This program is distributed in the hope that it will be useful, but WITHOUT ANY
  WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
  PARTICULAR PURPOSE.  See the GNU General Public License for more details.
  Email: cekuma1@gmail.com

""" 

import os
import shutil
import numpy as np
import copy
import spglib
from ase import Atoms, units
from ase.io import read, write
from ase.calculators.vasp import Vasp
from ase.calculators.espresso import Espresso
from ase.optimize import LBFGS, BFGS 
from ase.geometry import cell_to_cellpar, cellpar_to_cell
from ase.spacegroup import get_spacegroup, crystal
from pathlib import Path
import json
from read_write import read_options_from_input,write_incar, read_incars, read_and_write_kpoints,load_structure,modify_incar_and_restart



options = read_options_from_input()
    
def remove_spurious_distortion(pos):
    # Normalize and orthogonalize the cell vectors
    cell_params = cell_to_cellpar(pos.get_cell())
    new_cell = cellpar_to_cell(cell_params)
    pos.set_cell(new_cell, scale_atoms=True)

    # Adjust atom positions
    pos.wrap()

    pos.center()

    return pos
    


class ChangeDir:
    def __init__(self, path):
        self.path = path
        self.original_path = os.getcwd()

    def __enter__(self):
        os.chdir(self.path)

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir(self.original_path)
        
        
def swap_axes_to_longest_c(pos):
    """
    Reorders the lattice vectors of the given structure (pos) such that the longest vector is always c-axis.

    Parameters:
    pos (ASE Atoms object): The atomic structure.

    Returns:
    ASE Atoms object: Updated structure with reordered lattice vectors.
    """
    a, b, c = pos.get_cell()
    lengths = [np.linalg.norm(a), np.linalg.norm(b), np.linalg.norm(c)]
    max_index = lengths.index(max(lengths))

    new_cell = [a, b, c]  
    new_cell[2], new_cell[max_index] = new_cell[max_index], new_cell[2]  

    if max_index == 0:
        new_cell[0], new_cell[1] = new_cell[1], new_cell[0]
    pos.set_cell(new_cell)

    return pos

    
def run_calculation_vasp(atoms, calculator_settings, fmax=0.02, max_retries=5, retry_count=0):
    try:
        if atoms.get_calculator() is None:
            atoms.set_calculator(Vasp(**calculator_settings))

        opt = LBFGS(atoms)
        opt.run(fmax=fmax)
        #atoms.get_potential_energy()
    except Exception as e:
        if retry_count < max_retries:
            new_fmax = 0.02 + 0.01 * retry_count
            print(f"Caught an exception: {e}")
            print("Modifying INCAR and restarting the calculation.")
            modify_incar_and_restart()

            atoms = read("POSCAR")  # Re-read atoms from POSCAR
            atoms.set_calculator(Vasp(**calculator_settings))  # Reset calculator
            run_calculation_vasp(atoms, calculator_settings, new_fmax, max_retries, retry_count + 1)
            
        else:
            print("Maximum number of retries reached. Exiting.")
    print("DFT Optimization Done!")




def string_to_tuple(s, dim="3D"):
    result = []
    i = 0
    while i < len(s):
        if s[i] == '-':
            # Ensure the next character is a digit and combine it with the minus sign
            if i + 1 < len(s) and s[i + 1].isdigit():
                result.append(-int(s[i + 1]))
                i += 2
        elif s[i].isdigit():
            result.append(int(s[i]))
            i += 1
        else:
            # Skip any non-digit, non-minus characters
            i += 1
    
    if dim == "2D" and len(result) > 2:
        # Remove the last element if dim is "2D" and there are more than 2 elements
        result = result[:2]

    return tuple(result)


def string_to_tupleold(s):
    result = []
    i = 0
    while i < len(s):
        if s[i] == '-':
            # Ensure the next character is a digit and combine it with the minus sign
            if i + 1 < len(s) and s[i + 1].isdigit():
                result.append(-int(s[i + 1]))
                i += 2
        elif s[i].isdigit():
            result.append(int(s[i]))
            i += 1
        else:
            # Skip any non-digit, non-minus characters
            i += 1
    return tuple(result)
    

def check_vasp_optimization_completed(atoms, mode="DFT", output_dir="OPT"):
    """
    Checks if the VASP optimization has already been completed.

    Parameters:
    atoms (Atoms): ASE Atoms object of the initial structure.
    mode (str): Mode of the optimization.
    output_dir (str): Directory where VASP output files are stored.

    Returns:
    bool: True if optimization is completed, False otherwise.
    """
    optimized = False
    contcar_file = os.path.join(output_dir, "CONTCAR")
    outcar_file = os.path.join(output_dir, "OUTCAR")

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    
    if os.path.isfile(contcar_file) and os.path.isfile(outcar_file):
        with open(outcar_file, "r") as f:
            content = f.read()
            if "reached required accuracy " in content:
                optimized_atoms = read(contcar_file)
                if set(atoms.get_chemical_symbols()) == set(optimized_atoms.get_chemical_symbols()):
                    print("DFT Optimization already completed. Skipping...")
                    optimized = True
                    write(os.path.join(output_dir, "CONTCAR"), atoms, format='vasp', direct=True)
                else:
                    print("Structures in CONTCAR and initial atoms object do not match. Proceeding with optimization...")

    return optimized



def find_qe_pseudopotentials(atoms, base_path="./potentials"):
    # Convert relative path to absolute path
    #base_path = os.path.abspath(base_path)
    base_path = Path(base_path).absolute()

    pseudopotentials = {}
    unique_symbols = set(atoms.get_chemical_symbols())

    for symbol in unique_symbols:
        potential_paths = [
            os.path.join(base_path, symbol + "_pdojo.upf"),
            os.path.join(base_path, symbol + ".UPF"),
            os.path.join(base_path, symbol + "pz-vbc.UPF"),
            os.path.join(base_path, symbol + "_sv.UPF"),
            os.path.join(base_path, symbol + ".upf")
        ]

        pp_file_path = next((path for path in potential_paths if os.path.exists(path)), None)

        if not pp_file_path:
            raise Exception(f"Pseudopotential for {symbol} not found in any of the expected directories!")

        pseudopotentials[symbol] = os.path.basename(pp_file_path)


    return pseudopotentials




def check_optimization_completed_qe(atoms, mode="DFT", output_dir="OPT"):
    """
    Checks if the DFT optimization has already been completed.

    Parameters:
    atoms (Atoms): ASE Atoms object of the initial structure.
    mode (str): Mode of the optimization.
    output_dir (str): Directory where output files are stored.

    Returns:
    bool: True if optimization is completed, False otherwise.
    """
    optimized = False
    output_file = os.path.join(output_dir, "espresso.pwo")
    structure_file = os.path.join(output_dir, "optimized_structure.cif")  

    if os.path.exists(output_dir):
        if os.path.isfile(output_file):
            with open(output_file, "r") as f:
                content = f.read()
                if "Final enthalpy" in content: 
                    if os.path.isfile(structure_file):
                        optimized_atoms = read(structure_file)
                        if set(atoms.get_chemical_symbols()) == set(optimized_atoms.get_chemical_symbols()):
                            print("DFT Optimization already completed. Skipping...")
                            optimized = True
                        else:
                            print("Structures in final structure file and initial atoms object do not match. Proceeding with optimization...")
                    else:
                        print("Optimized structure file not found. Proceeding with optimization...")
    else:
        os.mkdir(output_dir)

    return optimized



def update_qe_object(step_name, existing_qe_parameters, file_name="qe_input.in"):
    if os.path.exists(file_name):
        file_path = file_name
    elif os.path.exists(os.path.join('..', file_name)):
        file_path = os.path.join('..', file_name)
    else:
        raise FileNotFoundError(f"File '{file_name}' not found in the current or parent directory.")

    with open(file_path, 'r') as file:
        data = json.load(file)['steps']

    for step in data:
        if step['name'] == step_name:
            updated_qe_parameters = merge_qe_parameters(existing_qe_parameters, step['data'])
            return updated_qe_parameters

    raise ValueError(f"Step '{step_name}' not found in the file.")
    
    
    
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
    

def run_calculation_qe(atoms, qe_parameters, fmax=0.02, max_retries=5, retry_count=0):
    try:
        if atoms.get_calculator() is None:
            atoms.set_calculator(Espresso(**qe_parameters))

        opt = LBFGS(atoms)
        opt.run(fmax=fmax)
        # You can also obtain energy, forces, etc., as needed
        # energy = atoms.get_potential_energy()

    except Exception as e:
        if retry_count < max_retries:
            new_fmax = 0.02 + 0.01 * retry_count
            print(f"Caught an exception: {e}")
            print("Modifying QE parameters and restarting the calculation.")

            atoms = read("optimized_structure.traj")  # Re-read atoms from QE output
            atoms.set_calculator(Espresso(**qe_parameters))  # Reset calculator
            run_calculation_qe(atoms, qe_parameters, new_fmax, max_retries, retry_count + 1)
            
        else:
            print("Maximum number of retries reached. Exiting.")
    print("DFT Optimization Done!")
    


struct = options.get("structure_file")
atoms = load_structure(struct)
atoms = remove_spurious_distortion(atoms)
spg = get_spacegroup(atoms) 
#mode = options.get("code_type", "VASP")

                    
def optimize_structure_vasp(mode="DFT"):
    """
    Optimizes the given atomic structure based on the specified mode.

    Parameters:
    - atoms: The ASE Atoms object (the atomic structure).
    - mode: Optimization mode (either 'DFT' or 'MD').
    """
    from ase import Atoms


        
    if not os.path.exists("OPT"):
        os.mkdir("OPT")
        
    cwd = os.getcwd()
    write_incar('opt', cwd, output_dir='OPT')
    kpts, _ = read_and_write_kpoints('static', fileName="KPOINTS-sd", outputDirectory='OPT')
    incar_settings = read_incars("opt", "INCAR", "OPT")
    atoms.set_calculator(Vasp(xc='PBE', kpts=kpts, **incar_settings))


    # Perform structure optimization
    optimized = check_vasp_optimization_completed(atoms)
    with ChangeDir("OPT"):
        atoms.set_calculator(Vasp(xc='PBE', kpts=kpts, **incar_settings))
        calculator_settings = {'xc': 'PBE', 'kpts': kpts, **incar_settings}

        if not optimized: #and not use_saved_data:        
            run_calculation_vasp(atoms,calculator_settings)
            optimized = True
      
    optimized_atoms = Atoms(symbols=atoms.get_chemical_symbols(), positions=atoms.get_positions(), cell=atoms.get_cell(), pbc=True)
    structure_file = "OPT/optimized_structure.cif"
    write(structure_file, optimized_atoms)
    return optimized_atoms
    
    
    
    
def optimize_structure_qe(mode="DFT"):
    """
    Optimizes the given atomic structure based on the specified mode using Quantum ESPRESSO.

    Parameters:
    - mode: Optimization mode ('DFT' or 'MD').
    - options: Dictionary of options including structure file path and other parameters.
    """
    


    custom_options = options.get('custom_options', {})
    base_path = custom_options.get('potential_dir', "./potentials")
    os.environ["VASP_PP_PATH"] = os.path.abspath(base_path)

       
    pseudopotentials = find_qe_pseudopotentials(atoms, base_path=base_path)

    optimized = check_optimization_completed_qe(atoms)
    kpts, _ = read_and_write_kpoints('static', fileName="KPOINTS-sd", outputDirectory='OPT')
    #kpts = [2, 2, 1]
    
    qe_parameters = {
        'input_data': {
            'control': {
                'calculation': 'vc-relax',
                'restart_mode': 'from_scratch',
                'pseudo_dir': base_path,
                'tstress': True,
                'tprnfor': True,
                'forc_conv_thr': 0.001,
                'outdir': './OPT'
            },
            'system': {
                'ecutwfc': 50,
                'ecutrho': 600,
                'occupations': 'smearing',
                'smearing': 'mp',
                'degauss' : 0.02,

            },           
            'electrons': {
                'conv_thr': 1e-8
            },
          'cell': {
              'cell_dofree': '2Dshape',
              'press' : 0.0,
              'press_conv_thr' : 0.5
          },
          'ions': {},  # Initialize 'ions' key here
        },
        'pseudopotentials': pseudopotentials,
        'kpts': kpts,
    }


    with ChangeDir("OPT"):
        qe_parameters = update_qe_object("DFT Optimization", qe_parameters)
        atoms.set_calculator(Espresso(**qe_parameters))
        calculator_settings = qe_parameters
        optimized_atoms = atoms.copy()
        
                
        if not optimized: #and not use_saved_data:        
            run_calculation_qe(optimized_atoms,calculator_settings)
            optimized = True

    optimized_atoms = Atoms(symbols=atoms.get_chemical_symbols(), positions=atoms.get_positions(), cell=atoms.get_cell(), pbc=True)
    structure_file = "OPT/optimized_structure.cif"
    write(structure_file, optimized_atoms)
    return optimized_atoms

