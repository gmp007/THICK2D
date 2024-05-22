"""
  THICK-2D -- Thickness Hierarchy Inference & Calculation Kit for 2D materials

  This program is free software; you can redistribute it and/or modify it under the
  terms of the GNU General Public License as published by the Free Software Foundation
  version 3 of the License.

  This program is distributed in the hope that it will be useful, but WITHOUT ANY
  WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
  PARTICULAR PURPOSE.  See the GNU General Public License for more details.
  
  Email: cekuma1@gmail.com

""" 
import os
import pandas as pd
import numpy as np
import joblib
from ase import Atoms
import re
from math import gcd
import periodictable
from read_write import read_options_from_input
from sklearn.model_selection import train_test_split, ShuffleSplit, cross_val_score
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor, AdaBoostRegressor
from sklearn.tree import DecisionTreeRegressor, ExtraTreeRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
#from xgboost import XGBRFRegressor
from catboost import CatBoostRegressor
from sklearn import metrics
from pymatgen.core.composition import Composition
from matminer.featurizers.composition import ElectronAffinity, ElementFraction
from matminer.featurizers.composition import ElementProperty, ValenceOrbital, ElectronegativityDiff
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from numpy import cross, linalg
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' 
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

from tensorflow.keras.models import load_model
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, initializers, regularizers  # <-- Added regularizers
from tensorflow.keras.layers import Dropout, BatchNormalization, GaussianNoise,Activation  # <-- Added Dropout and BatchNormalization
from tensorflow.keras.callbacks import ReduceLROnPlateau, EarlyStopping, ModelCheckpoint
from sklearn.metrics import r2_score
from sklearn.model_selection import RandomizedSearchCV,GridSearchCV
from bayes_opt import BayesianOptimization
from tensorflow.keras.optimizers import Adam,Adadelta, RMSprop, Adagrad, SGD, Nadam
from tensorflow.keras.callbacks import LearningRateScheduler 



#Suppress some tf warnings
tf.get_logger().setLevel('ERROR')




options = read_options_from_input()
#print("options", options)
#dnn_gan = options.get("use_dnn", False)
model_type = options.get("model_type", "classic").lower() 
nlayers = options.get("nlayers", 1)
vdwgap = options.get("vdwgap",3.5)
use_ml_model = options.get("use_ml_model",False)
num_augmented_samples = int(options.get("num_augmented_samples", 50))
add_thickness_data = options.get("add_thickness_data",False)
user_data_path = os.path.join(os.getcwd(), 'mat_thickness.txt')


if add_thickness_data:
    use_ml_model = False
    
#print("add_thickness_data", add_thickness_data, use_ml_model)
#exit(0)
rndseem=101
test_size = 0.20

def predict_thickness_2D(atoms, dir_modeldsave,num_augmented_samples):
    # Load the existing data
    existing_data = load_thickness()
    if add_thickness_data:
        user_thickness_data = load_user_thickness_data(user_data_path)
        existing_data = augment_and_average_thickness_data(existing_data, user_thickness_data)


    # Get the chemical formula of the new data point
    chem_formula = atoms.get_chemical_formula(mode='hill', empirical=False)
    chem_formula = simplify_formula(chem_formula)
    box_width = 85 
    # Check if the material already exists in the existing data
    #if chem_formula in existing_data['MaterialName'].values:
    #    existing_thickness = existing_data[existing_data['MaterialName'] == chem_formula]['Thickness_Ang'].iloc[0]
    #    print(f"Thickness for {chem_formula} is {existing_thickness} Å.".center(box_width, '-'))
    #    return existing_thickness

    
    # Process and scale the existing data for training
    processed_existing_data = process_dataframe(existing_data)
    X_scaled_existing, y_existing, scaler, train_columns = scale_dataframe(processed_existing_data)

    #joblib.dump(scaler, 'scaler.save')  # Save the scaler
    #joblib.dump(train_columns, 'train_columns.save')


    h5_model_path = os.path.join(dir_modeldsave, 'best_thickness_model.keras')
    pkl_model_path = os.path.join(dir_modeldsave, 'best_thickness_model.pkl')

    model = None
    if use_ml_model:
        model_loaded = False  # Flag to check if the model is loaded

        if model_type =="dnn" and os.path.exists(h5_model_path):    
            model = load_model(h5_model_path)
            print("Using saved DNN model to predict thickness.")
            model_loaded = True
        elif model_type == "classic" and os.path.exists(pkl_model_path):
            model = joblib.load(pkl_model_path)
            print("Using saved non-DNN model to predict thickness.")
            model_loaded = True
        else:
            print("Pretrained model does not exist, proceeding with full training...")

        # If the model is not loaded due to absence of pre-trained models, train a new model
        if not model_loaded:
            model_metrics, model = train_and_save_best_model(X_scaled_existing, y_existing, dir_modeldsave, num_augmented_samples, model_type)
            print(f"Metrics of the trained models are:\n, {model_metrics}\n")
    else:
        model_metrics, model = train_and_save_best_model(X_scaled_existing, y_existing, dir_modeldsave, num_augmented_samples, model_type)

        print(f"Metrics of the trained models are:\n, {model_metrics}\n")
        print("Best model used in prediction")

    processed_single_data = process_dataframe(pd.DataFrame([chem_formula], columns=['MaterialName']))
    X_scaled_single, _, _, _ = scale_dataframe(processed_single_data, scaler=scaler, train_columns=train_columns)

    
    if model_type =="dnn":
        X_scaled_single = X_scaled_single.to_numpy()
        
    predictions = model.predict(X_scaled_single)
    
    if nlayers > 1:
        predictions = vdwgap + predictions * nlayers

    # Return the predictions
    return predictions




def simplify_formula(formula):
    # Parse the formula into elements and their counts
    elements = re.findall('([A-Z][a-z]*)(\d*)', formula)
    elements = {element: int(count) if count else 1 for element, count in elements}

    # Find the greatest common divisor of the counts
    common_divisor = gcd(*elements.values())

    # Simplify the formula
    simplified_formula = ''.join(f"{element}{(count // common_divisor) if count > common_divisor else ''}" 
                                 for element, count in elements.items())
    
    return simplified_formula
    
    


def process_dataframeold(data):
    data = pd.DataFrame(data)
    # Create Composition objects
    Comp = [Composition(value) for value in data["MaterialName"]]
    data.loc[:, 'Composition'] = Comp

    # Featurize the dataframe using ElementFraction
    ef = ElementFraction()
    data = ef.featurize_dataframe(data, 'Composition')
    data = data.loc[:, (data != 0).any(axis=0)]

    # Define the molecular_weight function
    def molecular_weight(formula):
        try:
            elements = re.findall(r'([A-Z][a-z]*)(\d*)', formula)
            weight = 0
            for element, count in elements:
                count = int(count) if count else 1
                weight += getattr(periodictable, element).mass * count
            return weight
        except AttributeError:
            print(f"Warning: Element not found in formula {formula}")
            return None

    # Calculate molecular weights and add them as a new column
    data['MolWeight'] = data["MaterialName"].apply(molecular_weight)

    return data
    


def process_dataframe(data):
    data = pd.DataFrame(data)
    # Create Composition objects
    Comp = [Composition(value) for value in data["MaterialName"]]
    data.loc[:, 'Composition'] = Comp

    # Featurize the dataframe using ElementFraction
    ef = ElementFraction()
    vo = ValenceOrbital()
    data = ef.featurize_dataframe(data, 'Composition', ignore_errors=True)
    data = vo.featurize_dataframe(data, 'Composition', ignore_errors=True)
    data = data.loc[:, (data != 0).any(axis=0)]
    data = data.dropna(axis=1, how='all')  # Drop columns where all values are NaN
    data = data.dropna()  # Drop rows where any value is NaN
    
    # Define the molecular_weight function
    def molecular_weight(formula):
        try:
            elements = re.findall(r'([A-Z][a-z]*)(\d*)', formula)
            weight = 0
            for element, count in elements:
                count = int(count) if count else 1
                weight += getattr(periodictable, element).mass * count
            return weight
        except AttributeError:
            print(f"Warning: Element not found in formula {formula}")
            return None

    # Calculate molecular weights and add them as a new column
    data['MolWeight'] = data["MaterialName"].apply(molecular_weight)

    return data

def scale_dataframe(df, scaler=None, train_columns=None):
    if 'Thickness_Ang' in df.columns:
        X = df.drop(columns=["Thickness_Ang", "MaterialName", "Composition"], axis=1)
        y = df["Thickness_Ang"]
    else:
        X = df.drop(columns=["MaterialName", "Composition"], axis=1)
        y = None

    if scaler is None:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        train_columns = list(X.columns)  # Ensure train_columns is a list
    else:
        # Check if train_columns is provided
        if train_columns is None:
            raise ValueError("train_columns must be provided for scaling prediction data.")
        
        # Ensure the new data has the same columns as the training data
        missing_cols = set(train_columns) - set(X.columns)
        for col in missing_cols:
            X[col] = 0  # Add missing columns with default value (e.g., 0)
        X = X[train_columns]  # Reorder columns to match training data
        X_scaled = scaler.transform(X)

    X_scaled_df = pd.DataFrame(X_scaled, columns=train_columns)
    return X_scaled_df, y, scaler, train_columns


    

def scale_dataframeold(df,scale_df=False):
    

    if 'Thickness_Ang' in df.columns:
        X = df.drop(columns=["Thickness_Ang", "MaterialName", "Composition"], axis=1)
        y = df["Thickness_Ang"]
    else:
        X = df.drop(columns=["MaterialName", "Composition"], axis=1)
        y = None  


    if scale_df:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X_scaled_df = pd.DataFrame(X_scaled, columns=X.columns)
    else:
        X_scaled_df = X 

    return X_scaled_df, y



def train_and_save_best_model(X, Y, directory, num_augmented_samples, model_type, test_size=test_size, rndseem=rndseem):

    if model_type == "classic":
        print("Training non-DNN model to predict 2D thickness ...! Be patient ...")
    elif model_type == "dnn":
        print("Training DNN model to predict 2D thickness ...! Be patient ...")
    X_train_n, X_test, y_train_n, y_test = train_test_split(X, Y, test_size=test_size, random_state=rndseem)
     
    if model_type == "dnn":
        epochs = 1000
        optimize_noise = False
        data_agumentation = True
        early_stopping = True
        best_noise = 0.08
        num_augmented_samples = num_augmented_samples*10
        hidden_layers=(4, 400)
        algorithms = pd.DataFrame()

        nn_temp = CustomDNN(input_dim=X_train_n.shape[1], output_dim=1,
                                      hidden_layers=hidden_layers, activation='relu', optimizer='adam', noise_std=best_noise, #RMSprop
                                      epochs=epochs, optimize_noise=False)


        model_checkpoint_path = os.path.join(directory, 'best_thickness_model.keras')
        if data_agumentation:
          X_train_np = X_train_n.to_numpy()
          y_train_np = y_train_n.to_numpy()
          augmenter = DataAugmenterDNN(mean=0, std=best_noise, num_augmented_samples=num_augmented_samples)
          augmented_X_train, augmented_y_train = augmenter.augment_and_shuffle(X_train_np, y_train_np)

          if optimize_noise:
            X_train_main, X_val, y_train_main, y_val = train_test_split(augmented_X_train, augmented_y_train, test_size=test_size, random_state=rndseem)
            best_noise,best_node = nn_temp.find_best_noise(X_train_main, y_train_main, X_val, y_val)
            print(f"Best noise value: {best_noise}")
            hidden_layers=(hidden_layers[1], best_node)
            epochs = int(best_node)
            best_noise = best_noise
          else:
            best_noise = best_noise #Default value


          # Instantiate the custom neural network
          model_nn = CustomDNN(input_dim=X_train_n.shape[1], output_dim=1,
                                  hidden_layers=hidden_layers, activation='relu', noise_std=best_noise,
                                  epochs=epochs, optimize_noise=optimize_noise)
          mdl_history,best_model = model_nn.train(augmented_X_train, augmented_y_train, X_test, y_test, model_checkpoint_path=model_checkpoint_path, early_stopping=early_stopping, epochs=epochs)
          y_pred_train = model_nn.predict(augmented_X_train)
          r2_train = model_nn.r2_score(y_pred_train, augmented_y_train)
        else:

          if optimize_noise:
            X_train_main, X_val, y_train_main, y_val = train_test_split(X_main, y_main, test_size=test_size, random_state=rndseem)
            best_noise,best_node = nn_temp.find_best_noise(X_train_main, y_train_main, X_val, y_val)
            print(f"Best noise value: {best_noise}")
            hidden_layers=(hidden_layers[1], best_node)
            epochs = int(best_node)
            best_noise = best_noise
          else:
            best_noise = best_noise #Default value

            # Instantiate the custom neural network
          model_nn = CustomDNN(input_dim=X_train_n.shape[1], output_dim=y_train_n.shape[1],
                                  hidden_layers=hidden_layers, activation='relu', noise_std=best_noise,
                                  epochs=epochs, optimize_noise=optimize_noise)
          mdl_history = model_nn.train(X_train_n, y_train_n, X_test, y_test, model_checkpoint_path=model_checkpoint_path, early_stopping=early_stopping, epochs=epochs) # 
          y_pred_train = model_nn.predict(X_train_n)
          r2_train = model_nn.r2_score(y_pred_train, y_train_n)
          #hist = pd.DataFrame(mdl_history.history)


        # Evaluate the model on the test set
        test_loss = model_nn.evaluate(X_test, y_test)

        y_pred = model_nn.predict(X_test)
        r2 = model_nn.r2_score(y_test, y_pred)
        best_model = model_nn

        algorithms = algorithms.append({
            'Model-Sc': round(r2_train * 100, 2),
            'Test-Sc': round(r2 * 100, 2),
            'MSE': round(test_loss[0], 2),
        }, ignore_index=True)

        if not os.path.exists(directory):
            os.makedirs(directory)

        print(f"DNN model saved to {directory}/best_thickness_model.keras")
                    
    elif model_type == "classic":
        augmenter = DataAugmenter(mean=0, std=0.1, num_augmented_samples=num_augmented_samples)
        X_train, y_train = augmenter.augment_and_shuffle(X_train_n, y_train_n)


        # Define models and their hyperparameters
        hyper_params_xgb = {
            'objective': 'reg:squarederror',
            'n_estimators': 1000,
            'eval_metric': mean_absolute_error
        }

        MLA = [
            RandomForestRegressor(),
            DecisionTreeRegressor(),
            ExtraTreesRegressor(),
          #  XGBRFRegressor(**hyper_params_xgb),
            AdaBoostRegressor(),
            GradientBoostingRegressor(),
            ExtraTreeRegressor(),
            CatBoostRegressor(loss_function='RMSE', silent=True)
        ]

        # Initialize variables to store results
        algorithms = pd.DataFrame()
        best_model = None
        best_score = -float('inf')

        cv = ShuffleSplit(n_splits=10, test_size=test_size + 0.1, random_state=rndseem)

        for model in MLA:
            try:
                Alg = model.__class__.__name__
                if Alg == 'XGBRFRegressor':
                    model.fit(X_train, y_train, eval_set=[(X_test, y_test)])
                else:
                    model.fit(X_train, y_train)

                cross_validation = cross_val_score(model, X_train, y_train, cv=cv, scoring='r2')
                mean_cv_score = cross_validation.mean()
                pred = model.predict(X_test)
                adj_R2 = 1 - (1 - model.score(X_train, y_train)) * (len(y_train) - 1) / (len(y_train) - X_train.shape[1] - 1)
                Train_Score = model.score(X_train, y_train)
                Test_Score = model.score(X_test, y_test)
                MSE = metrics.mean_squared_error(y_test, pred)
                MAE = metrics.mean_absolute_error(y_test, pred)
                STD = cross_validation.std()

                if mean_cv_score > best_score:
                    best_score = mean_cv_score
                    best_model = model

                algorithms = algorithms.append({
                    'Algorithm': Alg,
                    'Model-Sc': round(Train_Score * 100, 2),
                    'Adj-Sc': round(adj_R2 * 100, 2),
                    #'Test-Sc': round(Test_Score * 100, 2),
                    'CV-Sc': round(mean_cv_score * 100, 2),
                    'MSE': round(MSE, 2),
                    'MAE': round(MAE, 2),
                    'STD': round(STD, 2)
                }, ignore_index=True)

            except Exception as e:
                print(f"Exception occurred in {Alg}: {e}")
                pass

        # Save the best model
        if best_model is not None:
            #best_model.fit(X,Y)
            
            if not os.path.exists(directory):
                os.makedirs(directory)
            
            model_path = os.path.join(directory, 'best_thickness_model.pkl')
            joblib.dump(best_model, model_path)
            print(f"Best model saved to {model_path}")
        else:
            print("No best model found to save.")
            
            joblib.dump(best_model, f'{directory}/best_thickness_model.pkl') 

    else:
        print("Select the appropriate model_type between classic and dnn")
        exit(0)    
    return algorithms , best_model



def load_user_thickness_data(file_path):
    """
    Load thickness data provided by a user from a text file.
    
    Parameters:
    - file_path (str): The path to the text file containing the user's data.
    
    Returns:
    - pd.DataFrame: DataFrame containing the loaded data.
    """
    try:
        user_data = pd.read_csv(file_path, sep='\s+', comment='#', header=None, names=['MaterialName', 'Thickness_Ang'])
        return user_data
    except Exception as e:
        print(f"Error loading user data: {e}")
        return pd.DataFrame()  # Return an empty DataFrame on failure
        
        
def augment_and_average_thickness_data(original_data, new_data):
    # Combine the original and new datasets
    combined_data = pd.concat([original_data, new_data])

    avg_data = combined_data.groupby('MaterialName', as_index=False)['Thickness_Ang'].mean()
    print(f"{len(new_data)} new records added to the thickness database for ML training.")
    return avg_data


def load_thickness():

    data = {
        "MaterialName": ["C", "MoS2", "WS2", "MoSe2", "WSe2", "BN", "MoTe2", "WTe2", "NbSe2", "TaS2", 
                          "TaSe2", "Bi2Se3", "Bi2Te3", "SnS2", "SnSe2", "HfS2", "HfSe2", "ZrS2", "ZrSe2", "TiS2", 
                          "TiSe2", "ReS2", "ReSe2", "CuI", "P", "Bi2Te3", "NbSe2", "SnS2", "MoTe2", "WTe2", 
                          "NbSe2", "TaS2", "TaSe2", "FeSe", "NiTe2", "PtS2", "PtSe2", "PtTe2", "PdTe2", "VS2", 
                          "VSe2", "MnSe2", "CrS2", "CrSe2", "FePS3", "WS2", "InSe", "SiC", "Si", "Ge",
                          "ZnO", "ZnS", "ZnSe", "CdO", "CdS", "CdSe", "MgO",
                          "PbTe", "PbSe", "SnSe", "SnTe", "GeTe", "SiTe",
                          "GeSe", "SnSe", "SnTe", "GeTe","GeO",
                          ],
        "Thickness_Ang": [3.43, 6.5, 6.2, 6.7, 6.4, 3.4, 10.8, 9.9, 6.7, 6.4, 
                          6.6, 15, 16, 6.1, 6.5, 6.5, 6.8, 6.4, 6.7, 6, 
                          6.3, 7.2, 7, 2.8, 6.5, 12, 8, 5.8, 10.8, 9.9, 
                          6.7, 6.4, 6.6, 6.2, 7.27, 4.9, 5.9, 6.8, 6.8, 5.9, 
                          6.32, 6.8, 6.16, 6.6, 7.9, 6.2, 6.1, 3.1, 0.67, 0.67,
                          3.05, 3.45, 3.75, 3.4, 3.75, 3.95, 2.3,
                          6.35,  # Average of 6.2 - 6.5
                          5.95,  # Average of 5.8 - 6.1
                          5.55,  # Average of 5.4 - 5.7
                          5.85,  # Average of 5.7 - 6.0
                          5.15,  # Average of 5.0 - 5.3
                          4.85,   # Average of 4.7 - 5.0                          
                          5.55, 4.95, 5.05, 5.15, 4.35,
                          ]
        }



    df = pd.DataFrame(data)
    df_avg = df.groupby('MaterialName', as_index=False)['Thickness_Ang'].mean()
    data = df_avg.drop_duplicates(subset=['MaterialName'])

    #data = data.set_index('MaterialName')

    return data
    
    

    df = pd.DataFrame(data)
    df_avg = df.groupby('MaterialName', as_index=False)['Thickness_Ang'].mean()
    data = df_avg.drop_duplicates(subset=['MaterialName'])

    #data = data.set_index('MaterialName')

    return data


# Augment data to sparse dataset to improve performance
class DataAugmenter:
    def __init__(self, mean=0, std=0.10, num_augmented_samples=2):
        self.mean = mean
        self.std = std
        self.num_augmented_samples = num_augmented_samples

    def add_gaussian_noise(self, data):
        """Add Gaussian noise to data."""
        noise = np.random.normal(self.mean, self.std, data.shape)
        return data + noise

    def augment_data_continuous(self, X, y):
        """Generate noisy versions of each sample for continuous data."""
        augmented_X = []
        augmented_y = []

        for idx, (sample, label) in enumerate(zip(X.values, y)):
            for _ in range(self.num_augmented_samples):
                noisy_sample = self.add_gaussian_noise(sample)
                augmented_X.append(noisy_sample)
                augmented_y.append(label)

        # Create DataFrame from augmented data
        augmented_X_df = pd.DataFrame(augmented_X, columns=X.columns)
        if isinstance(y, pd.Series):
            augmented_y_df = pd.Series(augmented_y, name=y.name)
        else:
            augmented_y_df = pd.DataFrame(augmented_y, columns=y.columns)

        return augmented_X_df, augmented_y_df

    def shuffle_dataset(self, X, y):
        """Shuffle data and labels."""
        combined = pd.concat([X, y], axis=1)
        shuffled = combined.sample(frac=1).reset_index(drop=True)
        return shuffled[X.columns], shuffled[y.name] if isinstance(y, pd.Series) else shuffled[y.columns]

    def augment_and_shuffle(self, X, y):
        augmented_X, augmented_y = self.augment_data_continuous(X, y)
        return self.shuffle_dataset(augmented_X, augmented_y)
        


class DataAugmenterDNN:
    def __init__(self, mean=0, std=0.10, num_augmented_samples=2):
        self.mean = mean
        self.std = std
        self.num_augmented_samples = num_augmented_samples

    def add_gaussian_noise(self, data):
        """Add Gaussian noise to data."""
        noise = np.random.normal(self.mean, self.std, data.shape)
        return data + noise

    def augment_data_continuous(self, X, y):
        """Generate noisy versions of each sample for continuous data."""
        augmented_X = []
        augmented_y = []

        for sample, label in zip(X, y):
            for _ in range(self.num_augmented_samples):
                noisy_sample = self.add_gaussian_noise(sample)
                augmented_X.append(noisy_sample)
                augmented_y.append(label)

        augmented_X = np.array(augmented_X)
        augmented_y = np.array(augmented_y)

        return augmented_X, augmented_y

    def shuffle_dataset(self, X, y):
        """Shuffle data and labels."""
        indices = np.arange(X.shape[0])
        np.random.shuffle(indices)
        return X[indices], y[indices]

    def augment_and_shuffle(self, X, y):
        augmented_X, augmented_y = self.augment_data_continuous(X, y)
        return self.shuffle_dataset(augmented_X, augmented_y)

class CustomDNN:
    def __init__(self, input_dim, output_dim, hidden_layers=(3, 500), activation='relu', loss='mae', optimizer='adam', noise_std=0.1, epochs=5000, optimize_noise=False):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.hidden_layers = hidden_layers
        self.activation = activation
        self.loss = loss
        self.noise_std = noise_std
        self.optimizer = optimizer
        self.n_layers = hidden_layers[0]
        self.nodes_per_layer = hidden_layers[1]
        self.epochs = epochs  # Number of epochs to train the model
        # Initialize optimize_noise
        self.optimize_noise = optimize_noise

        self.best_noise = self.noise_std
        if self.optimize_noise:
            self.best_noise_tmp, _ = self.find_best_noise(X_train_main, y_train_main, X_val, y_val)
            self.best_noise = self.best_noise_tmp

        self.model = self.build_model()

    def create_model_noise(self, noise_amount=None, nodes=None):
        if noise_amount is None:
            noise_amount = getattr(self, 'best_noise', 0.10)
        if nodes is None:
            nodes = self.nodes_per_layer

        model_noise = keras.Sequential()

        # Input layer with added Gaussian Noise
        model_noise.add(GaussianNoise(noise_amount, input_shape=(self.input_dim,)))

        # Hidden layers
        for _ in range(self.n_layers):
            model_noise.add(layers.Dense(self.nodes_per_layer, activation=self.activation))

        # Output layer
        model_noise.add(layers.Dense(self.output_dim))

        # Compile the model
        model_noise.compile(optimizer=self.optimizer, loss=self.loss, metrics=['mse'])

        return model_noise

    def find_best_noise(self, X_train_main, y_train_main, X_val, y_val):
        def objective(noise_amount, nodes):
            nodes = int(nodes)
            model_find_best_noise = self.create_model_noise(noise_amount=noise_amount, nodes=nodes)
            history = model_find_best_noise.fit(X_train_main, y_train_main, validation_data=(X_val, y_val), epochs=self.epochs, verbose=0)
            return history.history['val_loss'][-1]

        pbounds = {
            'noise_amount': (0.01, 0.10),
            'nodes': (50, 400)
        }

        optimizer = BayesianOptimization(
            f=objective,
            pbounds=pbounds,
            random_state=1,
        )

        optimizer.maximize(init_points=5, n_iter=15)
        best_noise = optimizer.max['params']['noise_amount']
        best_nodes = optimizer.max['params']['nodes']

        print(f"Best noise amount: {best_noise:.4f}")
        print(f"Best nodes: {int(best_nodes)}")

        #print(optimizer.max)
        return best_noise,best_nodes

    def build_model(self):
        np.random.seed(rndseem)
        initializer = initializers.RandomNormal(stddev=0.01, seed=rndseem)
        noise_std = getattr(self, 'best_noise', 0)

        # Create the model
        model = keras.Sequential()
        model.add(layers.Dense(self.nodes_per_layer, input_dim=self.input_dim, activation=None,  # No activation here
                          kernel_initializer=initializer, name="layer1",
                          kernel_regularizer=regularizers.L1L2(l1=1e-4, l2=1e-3),
                          bias_regularizer=regularizers.L2(1e-3),
                          activity_regularizer=regularizers.L2(1e-4)))

        if noise_std > 0:
          model.add(GaussianNoise(noise_std))  # Add Gaussian noise
        model.add(Activation(self.activation))  # Activation here
        model.add(BatchNormalization())  # Add batch normalization

        for i in range(1, self.n_layers):
            model.add(layers.Dense(self.nodes_per_layer, activation=None,  # No activation here
                                  kernel_initializer=initializer, name=f"layer{i + 1}"))
            if noise_std > 0:
              model.add(GaussianNoise(noise_std))  # Add Gaussian noise for each hidden layer
            model.add(Activation(self.activation))  # Activate
            model.add(BatchNormalization())  # Add batch normalization for hidden layers
            model.add(Dropout(0.25))  # Add dropout to prevent overfitting
        model.add(layers.Dense(self.output_dim, name="output_layer"))

        model.compile(loss=self.loss, optimizer=self.optimizer, metrics=['mse'])

        return model


    def preprocess_data(self, X, y):
        # Scale the targets
        sc_y = StandardScaler()
        df_names = y.columns
        y_scaled = sc_y.fit_transform(y)
        y_scaled = pd.DataFrame(y_scaled, columns=df_names)

        # Scale the features
        sc_X = StandardScaler() #MinMaxScaler()
        df_names_x = X.columns
        X_scaled = sc_X.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=df_names_x)
        # Save the scalers for inverse transforming later, if needed
        self.scaler_X = sc_X
        self.scaler_y = sc_y
        return X_scaled, y_scaled

    def train(self, X_train, y_train, X_val=None, y_val=None, patience=25, model_checkpoint_path="best_thickness_model.keras", early_stopping=False,epochs=None):
        """
        Train the neural network model.
        """
        if epochs is None:
          epochs = self.epochs
        #X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=rndseem)

        if X_val is None or y_val is None:
            validation_data = None
        else:
            validation_data = (X_val, y_val)

        callbacks = []
        if early_stopping:
            es = EarlyStopping(verbose=1, patience=patience)
            callbacks.append(es)

        lrd = ReduceLROnPlateau(monitor='val_loss',
                        factor=0.20,  # Reduce the learning rate by
                        patience=patience,
                        verbose=1,
                        mode='min',
                        threshold_mode='rel',
                        min_delta=1e-4,  # Minimum change to consider as improvement
                        cooldown=5,  # Wait for 5 epochs before potentially applying further reductions
                        min_lr=1e-6)  # Set a floor for the learning rate

        model_checkpoint = ModelCheckpoint(model_checkpoint_path, save_best_only=True, save_weights_only=False, monitor='val_loss', mode='min', verbose=1)
        #self.model.save(model_checkpoint_path)
        callbacks.extend([lrd, model_checkpoint]) #, self.lr_scheduler

        mdl_history = self.model.fit(X_train, y_train,
                                     epochs=epochs,
                                     validation_data=validation_data,
                                     shuffle = True,
                                     batch_size = 64,
                                     callbacks=callbacks)
        self.model.load_weights(model_checkpoint_path)

        return self.model, mdl_history

    def plot_loss(self, history, filename=None):
        plt.plot(history.history['loss'], label='Train Loss')
        plt.plot(history.history['val_loss'], label='Validation Loss')
        plt.xlabel('Epoch')
        plt.ylabel('Error')
        plt.legend()
        plt.grid(True)

        if filename:
            plt.savefig(filename, dpi=400, bbox_inches='tight')

        plt.show()



    def improved_plot_loss(self, history, title="Model Loss", xlabel="Epoch", ylabel="Error",
                          fontsize=14, linewidth=2.5, figure_size=(10, 6), show_grid=False,filename=None):
        """
        Plot the training and validation loss with improved visual features.

        Args:
        - history (History object): History object containing training/validation loss data.
        - title (str): Title for the plot.
        - xlabel (str): X-axis label.
        - ylabel (str): Y-axis label.
        - fontsize (int): Base fontsize for the title, labels, ticks, and legend.
        - linewidth (float): Line width of the plot lines.
        - figure_size (tuple): Figure size.
        - filename (str or None): If a string is provided, the plot will be saved to the given filename.

        Returns:
        - None: Displays the plot.
        """
        plt.figure(figsize=figure_size)
        plt.tick_params(axis='both', length=5, width=2)
        # Grid settings
        if show_grid:
            plt.rcParams['axes.grid'] = True
            plt.rcParams['grid.linestyle'] = '--'
            plt.rcParams['grid.linewidth'] = 0.5
        else:
            plt.rcParams['axes.grid'] = False

        plt.rcParams.update({'font.size': fontsize})


        plt.plot(history.history['loss'], label='Train Loss', linewidth=linewidth)
        plt.plot(history.history['val_loss'], label='Validation Loss', linewidth=linewidth)

        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.legend()
        plt.gca().spines['bottom'].set_linewidth(1.5)
        plt.gca().spines['left'].set_linewidth(1.5)

        if filename:
            plt.savefig(filename, dpi=400, bbox_inches='tight')
        plt.show()


    def historytrend(self,mdl_history):
      #Check the losses
      hist = pd.DataFrame(mdl_history.history)
      hist['epoch'] = mdl_history.epoch
      return hist.tail()


    def evaluate(self, X_test, y_test):
        test_loss = self.model.evaluate(X_test, y_test)
        return test_loss

    def predict(self, X_test):
        return self.model.predict(X_test)

    def r2_score(self, y_true, y_pred):
        return r2_score(y_true, y_pred)

    def compute_shap_values(self, X, sample_size=100):
        """
        Compute SHAP values for the given dataset X.

        Args:
        - X (pd.DataFrame): The dataset for which SHAP values are to be computed.
        - sample_size (int): Number of samples to be used as background dataset for SHAP.

        Returns:
        - List of SHAP values for each target.
        """
        background = X.sample(sample_size)  # Sample a background dataset
        explainer = shap.DeepExplainer(self.model, background.values)
        #explainer = shap.GradientExplainer(self.model, background.values)
        shap_values = explainer.shap_values(X.values)
        return shap_values

    def plot_shap_values(self, shap_values, X, class_names=None, save_path=None):
        """
        Plot SHAP summary plots for given SHAP values and dataset X.

        Args:
        - shap_values (list): SHAP values computed using compute_shap_values method.
        - X (pd.DataFrame): The dataset for which SHAP values were computed.
        - class_names (list, optional): Names of the target classes for identification (only required for multi-output).
        - save_path (str, optional): Directory path where the plots should be saved. If None, plots won't be saved.
        """
        if class_names is None and isinstance(shap_values, list):
            class_names = [f"Target {i+1}" for i in range(len(shap_values))]

        if isinstance(shap_values, list):
            for i, shap_val in enumerate(shap_values):
                print(f"SHAP summary plot for target {i + 1}:")
                shap.summary_plot(shap_val, X, plot_type="bar",color=feature_colors,show=False)

                if save_path:
                    file_name = f"shap_summary_feature_importance_dnn_{i + 1}.png"
                    full_path = os.path.join(save_path, file_name)
                    plt.savefig(full_path, dpi=400, bbox_inches='tight')
                    plt.clf()  # Clear the current figure for the next one

            print("SHAP summary plot for all targets combined:")
            combined_shap_values = np.sum(np.abs(np.array(shap_values)), axis=0)
            print(combined_shap_values)
            shap.summary_plot(combined_shap_values, X, feature_names=X.columns, plot_type="bar", color=feature_colors, show=False)
            if save_path:
                full_path = os.path.join(save_path, "shap_summary_feature_importance_dnn_combined.png")
                plt.savefig(full_path, dpi=400, bbox_inches='tight')
        else:
            shap.summary_plot(shap_values, X,plot_type="bar",color=feature_colors,show=False)
            if save_path:
                full_path = os.path.join(save_path, "shap_summary_feature_importance_dnn.png")
                plt.savefig(full_path, dpi=400, bbox_inches='tight')




