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

import os
from datetime import datetime

def write_default_input(cwd,code_type):
    kpoints_content = """# Step: Static Calculation
0
G
4 4 1
0 0 0
# Step: Dynamical Calculation
0
G
4 4 1
0 0 0
"""
    # Write KPOINTS content to a file
    with open(os.path.join(cwd, "KPOINTS-sd"), "w") as kpoints_file:
        kpoints_file.write(kpoints_content)
    if code_type == "VASP":
    # INCAR content
         incar_content = """# Step: DFT Optimization
PREC    = Accurate
ENCUT   = 500
EDIFF   = 1e-6
EDIFFG  = -0.001
IBRION  = 2
ISIF    = 4
ISYM    = 2
NSW     = 300
ISMEAR  = 0
SIGMA   = 0.1
POTIM   = 0.1
PSTRESS = 0.001
LREAL   = False
NPAR    = 11
NSIM    = 4
ALGO    = Normal
IALGO   = 48
ISTART  = 0
LVDW	= True
IVDW	= 12
LCHARG  = .FALSE.
LPLANE  = .TRUE.
LWAVE   = .FALSE.
LVDW    = True
IVDW    = 12
"""
    elif code_type == "QE":
        qe_content = """{
  "steps": [
    {
      "name": "DFT Optimization",
      "data": {
        "input_data": {
          "control": {
            "calculation": "vc-relax",
            "restart_mode": "from_scratch",
            "pseudo_dir": "base_path",
            "tstress": true,
            "tprnfor": true,
            "forc_conv_thr": 0.00001,
            "outdir": "./OPT"
          },
          "system": {
            "ecutwfc": 60,
            "ecutrho": 600,
            "occupations": "smearing",
            "smearing": "mp",
            "degauss": 0.01,
            "vdw_corr": "dft-d"
          },
          "electrons": {
            "conv_thr": 1e-8
          },
          "cell": {
            "cell_dofree": "2Dshape",
            "press": 0.0,
            "press_conv_thr": 0.5
          },
          "ions": {
            "tolp": 1.0e-4
        },
        "pseudopotentials": "pseudopotentials",
        "kpts": "kpts"

        }
      }
    }
  ]
}
"""


    # Write INCAR content to a file
    if code_type == "VASP":
        with open(os.path.join(cwd, "INCARs"), "w") as incar_file:
            incar_file.write(incar_content)
    elif code_type == "QE":
        with open(os.path.join(cwd, "qe_input.in"), "w") as qe_file:
            qe_file.write(qe_content)



def write_default_ystool_in(cwd):
    if not os.path.exists(os.path.join(cwd, "thick2dtool.in")):
        
        ystool_in = """########################################
###  THICK2D  package input control   ###
########################################
#choose stress calculator: VASP/QE currently supported
code_type = vasp

# Method of AI/ML training: classic/dnn
model_type = classic

#Use pre-trained model
use_ml_model = False

#Running over many structures
throughput = False

#structure file name with .cif or .vasp
structure_file = filename.cif

# Optimize structure
optimize = False

#No of layers
nlayers = 1

# van der Waals gap
vdwgap = 3.5

#explicit potential directory
potential_dir = /potential

#Synthethic data for ML
num_augmented_samples = 50

#Augment thickness data from mat_thickness.txt
add_thickness_data = False

#job submission command
job_submit_command = vasp_cmd/pw.x > log
"""
        # Write to "elastool.in" file
        with open(os.path.join(cwd, "thick2dtool.in"), "w") as elin:
            elin.write(ystool_in)



def print_default_input_message_0():
    print("╔════════════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                                ║")
    print("║                       ♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥                       ║")
    print("║                ♥♥♥  Default thick2dtool.in template generated.  ♥♥♥            ║")
    print("║                 ♥♥ Modify and rerun thick2d -0 to generate other   ♥♥          ║")
    print("║                 ♥♥    important input files. Happy running :)    ♥♥            ║")
    print("║                       ♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥                       ║")
    print("║                                   Exiting...                                   ║")
    print("║                                                                                ║")
    print("╚════════════════════════════════════════════════════════════════════════════════╝")





def print_default_input_message_1():
    print("╔════════════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                                ║")
    print("║                               ♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥                                  ║")
    print("║                           ♥♥                    ♥♥                             ║")
    print("║                        ♥ All default inputs written to files. ♥                ║")
    print("║                        ♥ Modify according to dimensionality ♥                  ║")
    print("║                        ♥ and other criteria ♥                                  ║")
    print("║                        ♥       Happy running :)        ♥                       ║")
    print("║                           ♥♥                    ♥♥                             ║")
    print("║                               ♥♥♥♥♥♥♥♥♥♥♥♥♥♥♥                                  ║")
    print("║                                Exiting...                                      ║")
    print("║                                                                                ║")
    print("╚════════════════════════════════════════════════════════════════════════════════╝")


max_width = len("|WARNING: This is an empirical approx; validity needs to be checked !! |")

def print_line(ec_file,content, padding=1, border_char="|", filler_char=" "):
    content_width = int(max_width) - (2 * int(padding)) - 2  # Subtract 2 for the border characters
    content = content[:content_width]  # Ensure content doesn't exceed the width
    line = border_char + filler_char*padding + content.ljust(content_width) + filler_char*padding + border_char
    #print(line)  # Print the line to the console
    if ec_file:
        ec_file.write(line + "\n")
    else:
        print(line)    

        
        


def print_banner(version,code_type,method,ec_file=None):
    current_time = datetime.now().strftime('%H:%M:%S')
    current_date = datetime.now().strftime('%Y-%m-%d')
    conclusion_msg = f"Calculations started at {current_time} on {current_date}"

    message = f"Results using\nTHICK2D Version: {version}\n {code_type} code is used as a calculator\nto perform {method} simulations\n{conclusion_msg}"

    max_width = 80  # Define the maximum width for the banner

    print_line(ec_file,'❤' * (max_width - 2), padding=0, border_char='❤', filler_char='❤')
    for line in message.split('\n'):
        centered_line = line.center(max_width - 4)
        print_line(ec_file,centered_line, padding=1, border_char='❤')
    print_line(ec_file,'❤' * (max_width - 2), padding=0, border_char='❤', filler_char='❤')




def print_boxed_message(ec_file=None):
    header_footer = "+" + "-" * 78 + "+"
    spacer = "| " + " " * 76 + " |"

    # List of lines to be printed
    lines = [
        (" * CITATIONS *", True),
        ("If you have used THICK2D in your research, PLEASE cite:", False),
        ("", False),  # Space after the above line
        ("THICK2D: ", False),
        ("A computational toolkit for predicting the thickness of 2D materials, ", False),
        ("C.E. Ekuma, ", False),
        ("Computer Physics Communications xxx, xxx, (2024)", False),
        ("", False),

        ("", False),  # Blank line for separation
        ("THICK2D -- Thickness Hierarchy Inference & Calculation Kit for 2D Materials", False),
        ("for predicting thickness of 2D materials, C.E. Ekuma,", False),
        ("www.github.com/gmp007/thick2d", False)
    ]

    def output_line(line):
        if ec_file:
            ec_file.write(line + "\n")
        else:
            print(line)

    output_line(header_footer)
    
    for line, underline in lines:
        centered_line = line.center(76)
        output_line("| " + centered_line + " |")
        
        if underline:
            underline_str = "-" * len(centered_line)
            output_line("| " + underline_str.center(76) + " |")

    # Print footer of the box
    output_line(header_footer)
    

