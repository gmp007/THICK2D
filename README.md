# THICK2D -- Thickness Hierarchy Inference & Calculation Kit for 2D Materials

**`THICK2D`** is a Python-based computational toolkit designed to accurately predict the thickness of two-dimensional (2D) materials using only the crystal structure information. Utilizing state-of-the-art algorithms, advanced machine learning architecture, and integrating seamlessly with widely recognized electronic structure codes such as VASP and QE, **THICK2D** offers researchers a robust platform for the precise determination and analysis of thickness of 2D material.

## Feature and Importance of THICK2D
The thickness-dependent behavior of 2D materials is now recongnized as a fundamental property. The unique structure of 2D materials, characterized by their inherent vacuum along the z-axis, presents a challenge in directly measuring thickness. Yet, understanding the thickness is crucial for various applications, from electronics and energy storage to the development of new nanotechnologies. **THICK2D** addresses this challenge by leveraging advanced machine learning models, which are trained on experimentally determined thicknesses, to accurately predict the thickness of any 2D material. This innovative approach ensures **THICK2D**'s robustness, requiring only the crystal structure information for thickness prediction. For users seeking more precise analyses, **THICK2D** also offers the option to first optimize the structure using VASP or QE, enhancing the accuracy of thickness computation.


## THICK2D Calculators
Leveraging the power of VASP and QE, **`THICK2D`** ensures high-precision calculations. These electronic structure codes, coupled with the toolkit's advanced algorithms, allow for detailed material analysis, making **THICK2D** a valuable tool in the study of 2D materials.

## Installation
**THICK2D** is easy to install and supports various installation methods to accommodate different user preferences. The installation process automatically handles all dependencies.

1. **Using pip**:
   - Install the latest version of THICK2D using pip:
     ```
     pip install -U thick2d
     ```

2. **From Source Code**:
   - Download the source code:
     ```
     git clone [git@github.com:gmp007/thick2d.git]
     ```
   - Install THICK2D by navigating to the directory and running:
     ```
     pip install .
     ```

3. **Installation via setup.py**:
   - Use the `setup.py` script for installation:
     ```
     python setup.py install [--prefix=/path/to/install/]
     ```
   - This method is especially useful for users with restricted administrative privileges, such as on shared HPC systems.

## Usage and Running THICK2D

To get started with **THICK2D**, follow these steps:

1. **Create a Calculation Directory**:
   - Prepare a directory for your calculations.
   - Run `thick2d -0` to generate the main input template, `thick2dtool.in`.

2. **Configure Input Files**:
   - Adjust the generated files according to your project's needs, specifying the calculator (VASP or QE) and potential file directory (This is needed only if you want to optimize the structure before computing the thickness. The flag `optimize` must be set to true). A sample `thick2dtool.in` is as shown below.
     ```
      ########################################
      ###  THICK2D  package input control   ###
      ########################################
      #choose stress calculator: VASP/QE currently supported
      code_type = vasp
      
      # Method of AI/ML training
      use_dnn = False
      
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
     ```

3. **Start the Calculation**:
   - Launch **THICK2D** by running the command `thick2d` in your calculation direction to begin the thickness measurement process.
   - If you want to predict thickness for many structures, you can benefit from using the high-throughput option. 

For many structures or in high-throughput materials screening and design.

   - If you want to predict thickness for many structures, you can benefit from using the high-throughput option. Set the flag `throughput` to true.
   - Copy the accompanying pre-computed machine learning models into the folder `ml_model` or, if you have performed the machine learning training yourself, this folder is automatically generated in your working folder.
   - Run the auxiliary Python code as `python throughput_thickness_calc.py <cif_directory> <control_file_directory>`, where `<control_file_directory>` is the location of the `thick2dtool.in` main **THICK2D** control parameter.

For detailed instructions, refer to the examples provided with the toolkit.

## Citing THICK2D

If **THICK2D** contributes to your research, please cite:

```latex
@article{ekuma2024,
  title={THICK2D: Thickness Hierarchy Inference and Calculation Kit for 2D Materials},
  journal={Journal Name},
  volume={xx},
  pages={xx-xx},
  year={2024},
  doi={http://dx.doi.org/xx.xxxx/xxxxxx},
  author={Your Name and Collaborators},
}
```

```latex
@misc{PropertyExtractor,
  author = {Chinedu Ekuma},
  title = {THICK2D -- Thickness Hierarchy Inference & Calculation Kit for 2D Materials},
  year = {2024},
  howpublished = {\url{https://github.com/gmp007/thick2d}},
  note = {Open source computational toolkit using advanced machine learning to predict thickness of 2D-based materials},
}
```


## Contact Information
- [cekuma1@gmail.com](mailto:cekuma1@gmail.com)

We welcome your feedback and inquiries.

## License
This project is licensed under the GNU GPL version 3 - see the [LICENSE](LICENSE) file for details.

## License

This project is licensed under the GNU GPL version 3 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- This work was supported by the U.S. Department of Energy, Office of Science, Basic Energy Sciences under Award DOE-SC0024099.
