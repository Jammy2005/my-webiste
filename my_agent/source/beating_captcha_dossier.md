# Project Dossier: Beating Captchas with TensorFlow OCR

## 1. One-Sentence Summary

Beating Captchas with TensorFlow OCR is a deep-learning project that trains and evaluates a convolutional–recurrent neural network (CRNN) in TensorFlow to automatically decode CAPTCHA images into text using a custom OCR pipeline built on top of the `mltu` toolkit.

## 2. Executive Summary

This project implements an end-to-end CAPTCHA solving system focused on image-to-text recognition using TensorFlow 2. It reuses and extends components from the `mltu` framework (a collection of training utilities for TensorFlow and PyTorch) and customizes them for CAPTCHA images. The core workflow prepares a labeled CAPTCHA dataset, encodes labels into a vocabulary, builds a residual CNN + bidirectional LSTM architecture, trains it with CTC loss, exports the best model to ONNX, and evaluates it via a dedicated inference script that reports character error rate (CER) and allows ad hoc testing on individual images. The repository is structured to separate reusable training utilities (`mltu`) from the specific CAPTCHA task logic (`captcha_to_text`) and persists model artifacts and training metadata under a timestamped `Models/02_captcha_to_text/...` directory. While it is primarily a research/learning project inspired by an online tutorial, it demonstrates practical skills in constructing OCR pipelines, handling image datasets, configuring training runs, and integrating ONNX for portable deployment.

## 3. What Problem This Project Solves

The project addresses the problem of automatically recognizing text from noisy, distorted CAPTCHA images. Traditional CAPTCHAs are intentionally designed to be hard for simple OCR systems, using warped letters, interference lines, and variable fonts. This codebase builds a robust deep-learning-based OCR model that learns to map such images directly to text, handling variable-length outputs and character-level noise via CTC-based training. The goal is to train a model that generalizes well to new CAPTCHA samples and achieves high accuracy on realistic datasets.

## 4. Likely Users / Stakeholders

- **Machine learning practitioners and students**: People who want to learn how to build an OCR model for CAPTCHAs using TensorFlow and a custom training utility library.
- **Researchers or hobbyists working on CAPTCHA problems**: Individuals exploring robustness of OCR under adversarial or noisy image conditions.
- **Developers building automated testing or data collection tools**: Those who might need to decode CAPTCHAs in controlled environments, e.g., automated scraping of their own services or internal QA systems.
- **Portfolio reviewers, recruiters, and interviewers**: People evaluating the author’s ability to design and implement deep learning pipelines, manage datasets, and structure ML projects.

## 5. What the System Actually Does

- **Dataset construction**: The `train.py` script scans a directory of CAPTCHA images (`Datasets/captcha-images-v3`) and constructs a list of `(image_path, label)` pairs, where labels are inferred from image filenames.
- **Vocabulary and labeling**: It builds a character-level vocabulary from all labels and computes the maximum label length across the dataset.
- **Config management**: `ModelConfigs` in `configs.py` stores hyperparameters (image size, batch size, learning rate, epochs, etc.) and dynamically generates a timestamped model path for saving artifacts.
- **Data pipeline**: A `DataProvider` from `mltu.tensorflow.dataProvider` is configured with image readers, resizers, label indexers, and label padding transformers, and is split into training and validation providers, with augmentations applied to the training side.
- **Model architecture**: `model.py` defines a CRNN architecture: residual convolutional blocks (using `mltu.tensorflow.model_utils.residual_block`) for spatial feature extraction followed by bidirectional LSTMs and a softmax output head for per-time-step character predictions.
- **Training loop**: The model is compiled with Adam, CTC loss, and a character-level word error rate metric (`CWERMetric`), then trained with callbacks for early stopping, checkpoints, TensorBoard logging, learning-rate scheduling, training logs, and ONNX export (`Model2onnx`).
- **Artifact generation**: After training, CSV files describing the train/validation splits are saved under the model directory, along with model checkpoints and ONNX exports.
- **Inference and evaluation**: `evaluation_testing.py` loads an ONNX model via `ImageToWordModel`, runs predictions on test CSV entries, computes CER with `mltu.utils.text_utils.get_cer`, logs per-sample results, and reports the average CER, with an option to test a specific image path.

## 6. Technical Architecture

- **Training sub-system**:
  - Entrypoint: `captcha_to_text/train.py`.
  - Configuration: `captcha_to_text/configs.py` defines `ModelConfigs` that inherit from `mltu.configs.BaseModelConfigs`, including dynamically created timestamped `model_path`.
  - Dataset: Local directory `Datasets/captcha-images-v3` containing CAPTCHA images whose filenames encode ground-truth labels.
  - Data pipeline: `DataProvider` processes image/label pairs, applies preprocessing (`ImageReader`, `ImageResizer`) and label transformations (`LabelIndexer`, `LabelPadding`), and supports training/validation splits with augmentations (`RandomBrightness`, `RandomRotate`, `RandomErodeDilate`).
  - Model: Defined in `captcha_to_text/model.py` using Keras layers and `mltu.tensorflow.model_utils.residual_block`. The network stacks several residual blocks (increasing filters from 16 to 256) and reshapes the spatial map into a sequence for BLSTM layers.
  - Loss and metrics: Uses `CTCloss` from `mltu.tensorflow.losses` and `CWERMetric` from `mltu.tensorflow.metrics`.
  - Training orchestration: Keras training loop with callbacks (`EarlyStopping`, `ModelCheckpoint`, `TensorBoard`, `ReduceLROnPlateau`) plus custom callbacks from `mltu.tensorflow.callbacks` (`Model2onnx`, `TrainLogger`).

- **Inference / evaluation sub-system**:
  - Entrypoint: `captcha_to_text/evaluation_testing.py`.
  - Model loader: `ImageToWordModel` extends `mltu.inferenceModel.OnnxInferenceModel` to wrap ONNX inference and character decoding (`ctc_decoder`).
  - Evaluation flow: Loads model configs (`BaseModelConfigs.load` with a YAML path), wraps an ONNX model, iterates over a dataset described via CSV (`Datasets/test2.csv` or saved validation CSVs), computes predictions and CER per sample, and reports aggregate CER.

- **Supporting ML utility library (`mltu`)**:
  - Contains TensorFlow- and PyTorch-specific utilities in `mltu/tensorflow` and `mltu/torch`.
  - Provides reusable components: residual blocks, data providers, callbacks, metrics, losses, augmentors, and tokenizers.
  - Has its own small READMEs and requirements files for both TensorFlow and PyTorch usage.

The architecture is monolithic but modular: a single training script orchestrates components from `mltu` and custom configs/model definitions, with data and model artifacts organized in separate directories.

## 7. Main Components

- **`captcha_to_text/train.py`**: Main training script that:
  - Prepares dataset and vocabulary.
  - Initializes `ModelConfigs` and saves them to disk.
  - Sets up `DataProvider` with preprocessing, transformations, and augmentations.
  - Instantiates the CRNN model via `train_model`.
  - Compiles and fits the model with CTC loss and monitoring callbacks.
  - Outputs training artifacts (CSV splits, logs, Keras model, ONNX export).

- **`captcha_to_text/model.py`**:
  - Defines `train_model(input_dim, output_dim, activation="leaky_relu", dropout=0.2)`.
  - Builds a residual CNN backbone (five residual stages from 16 to 256 filters).
  - Reshapes the resulting feature map into a 2D sequence and passes it through two BLSTM layers with dropout.
  - Uses a final dense softmax layer with `output_dim + 1` classes (extra token for CTC blank or padding).

- **`captcha_to_text/configs.py`**:
  - Implements `ModelConfigs(BaseModelConfigs)` with:
    - `model_path` computed using current timestamp under `Models/02_captcha_to_text`.
    - Hyperparameters: `height`, `width`, `batch_size`, `learning_rate`, `train_epochs`, and `train_workers`.
    - Attributes for `vocab` and `max_text_length` that are filled and persisted at runtime.

- **`captcha_to_text/evaluation_testing.py`**:
  - Implements `ImageToWordModel` extending `OnnxInferenceModel`, with:
    - `predict(image)` method that resizes, normalizes, runs the ONNX model, and decodes outputs to text using `ctc_decoder`.
  - In its `__main__` block:
    - Loads a stored configuration YAML specifying model path and vocabulary.
    - Initializes an `ImageToWordModel` with the ONNX model.
    - Iterates over a CSV of image paths and labels, computing CER for each and the average.
    - Provides a small test harness for a manually specified image path.

- **`mltu` library modules** (selected examples):
  - `mltu/tensorflow/dataProvider.py`: Batch loading and preprocessing abstraction for TensorFlow models.
  - `mltu/preprocessors.py`, `mltu/transformers.py`, `mltu/augmentors.py`: Building blocks for reading, resizing, indexing, padding, and augmenting data.
  - `mltu/tensorflow/losses.py` and `mltu/tensorflow/metrics.py`: Provide `CTCloss` and `CWERMetric` tailored for sequence prediction tasks.
  - `mltu/tensorflow/callbacks.py`: Includes `Model2onnx` and `TrainLogger` to facilitate exporting models and logging training.
  - `mltu/inferenceModel.py`: Base ONNX inference wrapper that `ImageToWordModel` builds upon.

## 8. End-to-End Flow

1. **Dataset preparation**:
   - Place CAPTCHA images in `Datasets/captcha-images-v3` where each filename (without extension) encodes the ground-truth text.
   - `train.py` scans this directory and builds a `(image_path, label)` list.

2. **Configuration and vocabulary building**:
   - Instantiate `ModelConfigs()` which sets basic training hyperparameters and model output directory.
   - Accumulate a set of characters across all labels to form `configs.vocab`.
   - Determine the maximum label length (`configs.max_text_length`).
   - Save the configuration to disk (`configs.save()`), creating a YAML file in the `model_path` directory.

3. **Data provider setup**:
   - Build a `DataProvider` with:
     - `dataset` list as above.
     - `ImageReader(CVImage)` to read images.
     - `ImageResizer(configs.width, configs.height)` to normalize input dimensions.
     - `LabelIndexer(configs.vocab)` to convert string labels to integer indexes.
     - `LabelPadding(max_word_length=configs.max_text_length, padding_value=len(configs.vocab))` to create fixed-length label arrays.
   - Split the provider into training and validation sets (e.g., 90% train, 10% validation).
   - Apply augmentors to training batches (brightness, rotation, erosion/dilation).

4. **Model creation and compilation**:
   - Call `train_model(input_dim=(configs.height, configs.width, 3), output_dim=len(configs.vocab))` to instantiate the Keras model.
   - Compile with:
     - `optimizer=tf.keras.optimizers.Adam(learning_rate=configs.learning_rate)`.
     - `loss=CTCloss()`.
     - `metrics=[CWERMetric(padding_token=len(configs.vocab))]`.

5. **Training loop and callbacks**:
   - Define callbacks:
     - `EarlyStopping` on validation CER to prevent overfitting.
     - `ModelCheckpoint` to save the best `model.keras`.
     - `TrainLogger` to log training progress to `configs.model_path`.
     - `TensorBoard` callback for visualization.
     - `ReduceLROnPlateau` to adjust learning rate when validation CER plateaus.
     - `Model2onnx` to export the best model to ONNX.
   - Call `model.fit(train_data_provider, validation_data=val_data_provider, epochs=configs.train_epochs, callbacks=[...])`.

6. **Artifact saving**:
   - After training completes, export train and validation splits to CSV (`train.csv` and `val.csv`) in the model directory.
   - Model weights (`model.keras`), ONNX export, logs, and TensorBoard logs are stored under the same timestamped directory.

7. **Evaluation and ad hoc testing**:
   - Use `evaluation_testing.py` to:
     - Load `BaseModelConfigs` from the YAML file in a specific model directory.
     - Create `ImageToWordModel` pointing at that directory and using the stored vocabulary.
     - Load a CSV file (e.g., `Models/.../val.csv` or `Datasets/test2.csv`) listing image paths and labels.
     - For each sample, run inference, decode predictions to text, compute CER, and accumulate it.
     - Print the average CER over the dataset and optionally run a prediction on a manually specified image for quick inspection.

## 9. Tech Stack

- **Languages**:
  - Python 3 (inferred from TensorFlow, Keras, and library structure).

- **Frameworks and libraries**:
  - TensorFlow 2.10.1 and Keras for deep learning.
  - `mltu` (local package, version 1.2.5) providing training utilities, data providers, callbacks, metrics, augmentors, and ONNX inference wrappers.
  - ONNX and `tf2onnx` for model export.
  - NumPy for numerical operations.
  - OpenCV (`cv2`) for image loading and resizing in evaluation.
  - Pandas and `tqdm` in `evaluation_testing.py` for dataset handling and progress reporting.

- **Modeling patterns**:
  - Residual CNNs for feature extraction.
  - Bidirectional LSTMs for sequence modeling.
  - CTC loss for variable-length sequence alignment.

- **Environment / tooling**:
  - The project includes separate `requirements.txt` files under `mltu/tensorflow` and `mltu/torch` for environment setup of the utility library.
  - TensorBoard for training visualization.

## 10. Notable Engineering Decisions

- **Use of a residual CNN + BLSTM architecture**:
  - Combining residual convolutional layers with BLSTM layers is a standard yet effective pattern for OCR tasks, capturing both spatial and sequential dependencies.
  - The architecture scales filter counts from 16 to 256 and uses downsampling via strided residual blocks, balancing feature richness with computational cost.

- **CTC-based training for CAPTCHA text**:
  - The choice of CTC loss fits well with variable-length text outputs and removes the need for character-level alignment between inputs and labels.

- **Custom `mltu` training framework integration**:
  - Instead of writing ad hoc training loops and data pipelines, the author built on top of a reusable `mltu` library that abstracts data providers, transformers, augmentors, and callbacks.
  - This modularity makes it easier to adapt the pipeline to other OCR tasks or datasets.

- **Timestamped model directories**:
  - `ModelConfigs` uses a timestamp to create unique model directories under `Models/02_captcha_to_text/...`, improving experiment tracking and avoiding overwriting prior runs.

- **ONNX export and ONNX-based inference**:
  - The training pipeline includes a `Model2onnx` callback that automatically exports the model to ONNX.
  - Inference uses an ONNX runtime wrapper (`OnnxInferenceModel`), which decouples training from deployment and allows running the model in environments that support ONNX but not necessarily TensorFlow.

## 11. Evidence of Production Readiness

- **Positive signals**:
  - **Structured configuration and artifact management**: Use of a config class (`ModelConfigs`) and timestamped directories suggests attention to experiment organization.
  - **Callbacks and monitoring**: Early stopping, learning-rate scheduling, model checkpointing, TensorBoard logging, and ONNX export are typical of training setups that aim for repeatability and observability.
  - **Evaluation automation**: An explicit evaluation script (`evaluation_testing.py`) that computes CER on held-out data or dedicated test sets.
  - **Modular training utilities**: The `mltu` library abstracts common patterns, which is a step toward reusable infrastructure.

- **Limitations / missing production pieces**:
  - No unified top-level `requirements.txt` or environment specification for the entire project.
  - No web API, CLI packaging, or deployment scripts; usage is via direct script execution.
  - Hard-coded file system paths in `evaluation_testing.py` (absolute paths to previous experiments) indicate local experimentation rather than portable deployment.
  - No tests (unit/integration) or CI configuration are present in the repository.

Overall, the project is closer to a well-structured research/learning setup than a fully productized service.

## 12. Challenges the Developer Likely Had to Solve

- **Designing and tuning an OCR model for noisy CAPTCHAs**:
  - Choosing appropriate image dimensions, CNN depth, and BLSTM units to balance accuracy and training time.
  - Managing overfitting via data augmentation and early stopping.

- **Label and vocabulary handling**:
  - Inferring labels from filenames, building a character vocabulary, and encoding labels for CTC-based training.
  - Handling padding tokens and ensuring consistent decoding at inference time.

- **Data pipeline and augmentation**:
  - Creating a robust data provider that can efficiently load, preprocess, and augment images while feeding the GPU.

- **Experiment tracking and artifact management**:
  - Ensuring that each run saves configs, datasets splits, logs, and models in an organized folder structure.

- **ONNX conversion and inference**:
  - Ensuring a correct mapping between TensorFlow/Keras model definitions and ONNX exports.
  - Wrapping ONNX runtime for convenient prediction and decoding.

## 13. What Makes This Project Strong on a Resume

- **End-to-end deep learning pipeline**:
  - Demonstrates the ability to take a problem from data ingestion through model design, training, evaluation, and export.

- **OCR and sequence modeling experience**:
  - Shows familiarity with OCR-specific modeling patterns (CRNN + CTC) and character-level error metrics.

- **Reusability and modularity**:
  - Integration and extension of the `mltu` library show an understanding of reusable ML infrastructure and abstractions (data providers, callbacks, metrics, augmentors).

- **Experiment management and observability**:
  - Use of TensorBoard, checkpointing, early stopping, and structured configs underscores good ML engineering habits.

- **ONNX integration**:
  - Inclusion of ONNX export and ONNX-based inference aligns with modern deployment patterns and model portability practices.

When described clearly, these aspects communicate hands-on, practical experience with building ML systems, not just using high-level AutoML tools.

## 14. Limitations or Gaps

- **Lack of top-level environment specification**:
  - While there are `requirements.txt` files under `mltu/tensorflow` and `mltu/torch`, there is no consolidated environment description for the specific CAPTCHA project (e.g., one top-level `requirements.txt` or `pyproject.toml`).

- **Hard-coded paths and manual configuration**:
  - `evaluation_testing.py` has absolute paths pointing to local directories, which reduces portability.
  - The README notes “install dependencies (oops no requirements.txt)” and instructs manual path changes, indicating incomplete packaging.

- **No deployment surface**:
  - There is no REST API, CLI, or GUI to expose the model for external consumers.

- **Limited automation/testing**:
  - No automated tests, linting, or CI/CD configuration are present.
  - No scripting for dataset download and preparation (the dataset download code in `train.py` is commented out).

- **Partial reuse from tutorial**:
  - The README acknowledges that “a large portion of this code is taken from Python Lessons implementation,” so not all components are original, though the integration and customization are.

## 15. Best Future Improvements

- **Create a top-level environment spec**:
  - Add a root-level `requirements.txt` or `pyproject.toml` that includes TensorFlow, Keras, OpenCV, Pandas, `tqdm`, and `mltu` (either as a local package or via VCS).

- **Parameterize paths and configuration**:
  - Replace hard-coded absolute paths in `evaluation_testing.py` with relative paths or configuration flags.
  - Expose dataset location, model directory, and evaluation CSV paths via command-line arguments or environment variables.

- **Add a simple API or CLI interface**:
  - Build a lightweight CLI or REST API (e.g., FastAPI or Flask) that takes CAPTCHA images and returns predicted text, using the ONNX model.

- **Automate dataset download and preprocessing**:
  - Re-enable and generalize the dataset download code, with clean configuration for alternate datasets.

- **Add basic tests and documentation**:
  - Include tests for key utilities (e.g., label encoding/decoding, config loading, simple inference).
  - Extend the README with explicit setup commands, environment details, and example invocations of `train.py` and `evaluation_testing.py`.

- **Experiment tracking enhancement**:
  - Integrate with MLflow or a similar tool for more advanced tracking of runs, metrics, and artifacts if the project grows.

## 16. Recruiter-Friendly Summary

This project showcases an end-to-end deep learning pipeline for solving CAPTCHA images using TensorFlow and Keras, built around a custom residual CNN + BLSTM architecture trained with CTC loss. It demonstrates practical skills in building data pipelines, configuring and training models, managing experiment artifacts, exporting to ONNX, and evaluating sequence models with character-level metrics. The codebase is organized, readable, and grounded in standard ML engineering practices, making it a strong example of applied machine learning work suitable for inclusion in a portfolio.

## 17. Deep Technical Summary

The repository implements a character-level OCR system for CAPTCHA images, leveraging a CRNN architecture with residual CNN layers and BLSTMs, trained using CTC loss. The training script orchestrates dataset assembly from image filenames, vocabulary construction, configuration saving, and TensorFlow-based training using a custom `DataProvider` abstraction from `mltu`. Data augmentation (brightness, rotation, erosion/dilation) is applied to improve generalization, and the model is evaluated using a CWER metric suitable for sequence tasks. Artifacts are organized under timestamped directories containing configs, CSV splits, logs, Keras model files, and ONNX exports. Inference is managed via an ONNX runtime wrapper that handles resizing, normalization, and CTC decoding. Overall, the code reflects solid understanding of OCR architectures, sequence modeling, and practical ML tooling, with room for further hardening around deployment and environment management.

## 18. FAQ for Another AI Assistant

1. **Q:** What is the main goal of this project?  
   **A:** To train and evaluate a deep learning model that converts CAPTCHA images into text using a TensorFlow-based OCR pipeline built on a residual CNN + BLSTM architecture and CTC loss.

2. **Q:** Where is the primary training logic implemented?  
   **A:** In `captcha_to_text/train.py`, which prepares the dataset, initializes configs, builds data providers, constructs the model, and runs the Keras training loop with callbacks.

3. **Q:** How are labels and vocabularies handled?  
   **A:** Labels are inferred from image filenames in `Datasets/captcha-images-v3`; a set of characters is accumulated across all labels to form `configs.vocab`, and the maximum label length is stored in `configs.max_text_length` for padding.

4. **Q:** What does the model architecture look like?  
   **A:** Defined in `captcha_to_text/model.py`, it uses multiple residual convolutional blocks (16–256 filters) followed by reshaping into sequences and two Bidirectional LSTM layers, ending with a dense softmax output over `len(vocab) + 1` classes for CTC.

5. **Q:** How is the loss function defined?  
   **A:** The model uses `CTCloss` from `mltu.tensorflow.losses`, which is appropriate for sequence labeling problems with unaligned input-output pairs, such as OCR.

6. **Q:** How is model performance measured?  
   **A:** During training, `CWERMetric` from `mltu.tensorflow.metrics` tracks character-level word error rate; during evaluation, `evaluation_testing.py` uses `get_cer` to compute character error rate over a dataset and prints both per-sample and average CER.

7. **Q:** How are training artifacts organized?  
   **A:** `ModelConfigs` assigns a timestamped `model_path` folder under `Models/02_captcha_to_text/`, within which configs, logs, CSV splits, Keras models, and ONNX exports are stored.

8. **Q:** How is ONNX used in this project?  
   **A:** A `Model2onnx` callback exports the trained Keras model to ONNX, and `ImageToWordModel` in `evaluation_testing.py` uses `OnnxInferenceModel` to run inference on ONNX models with CTC decoding.

9. **Q:** How can the model be evaluated on new images?  
   **A:** Use `evaluation_testing.py` to load the appropriate model directory and vocabulary, provide a CSV of image paths and labels for batch evaluation, or modify the script’s “specific image” section to run predictions on individual image files.

10. **Q:** What are the biggest gaps if I want to turn this into a production service?  
    **A:** You would need a consolidated environment spec, removal of hard-coded paths, a stable inference API or CLI, logging and error handling around inference, automated tests, and possibly integration with model serving infrastructure.

11. **Q:** How reusable is the `mltu` library beyond this project?  
    **A:** `mltu` includes generic TensorFlow and PyTorch utilities—data providers, augmentors, callbacks, losses, metrics—that can be applied to other sequence or image tasks beyond CAPTCHA OCR.

12. **Q:** Does the project include any web or UI components?  
    **A:** No, all interaction happens via Python scripts run from the command line; there is no frontend or web API in the current codebase.

## 19. Confidence and Uncertainty Notes

- **High confidence**:
  - The project purpose (CAPTCHA OCR) and high-level architecture (residual CNN + BLSTM + CTC) are clearly documented in `README.md`, `model.py`, and `train.py`.
  - The description of data flow, training pipeline, and ONNX-based inference is directly grounded in the code.
  - The assessment that this is a research/learning-style project (rather than a production deployment) is supported by the lack of deployment code and the README language.

- **Medium confidence**:
  - Some inferred details about typical usage patterns (e.g., likely users, scenarios where this would be applied) are reasonable extrapolations rather than explicitly documented.
  - The assumption that Python 3 is used is based on standard TensorFlow requirements and modern code style, not an explicit version file.

- **Low confidence / unknown**:
  - Exact dataset size, training duration, and resource requirements are not specified.
  - Specific hyperparameter tuning history, experiments run, or comparisons with baseline models are not present in the repository, so any claims about performance beyond what is briefly mentioned in the README should be treated as approximate.

---

## Machine Summary

```json
{
  "project_name": "Beating Captchas with TensorFlow OCR",
  "project_type": "Deep learning OCR model for CAPTCHA image-to-text recognition",
  "summary_short": "End-to-end TensorFlow-based CRNN + CTC pipeline for solving CAPTCHA images, with training, evaluation, and ONNX export built on a custom ML utilities library.",
  "primary_language": ["Python"],
  "frameworks": ["TensorFlow 2.10.1", "Keras", "ONNX", "mltu"],
  "key_features": [
    "CRNN architecture with residual CNN and BLSTM layers",
    "CTC loss-based training for variable-length CAPTCHA text",
    "Configurable data pipeline with augmentation via mltu DataProvider",
    "Timestamped experiment directories with configs, logs, and model artifacts",
    "Automatic ONNX export and ONNX-based inference wrapper",
    "Evaluation script computing character error rate on test datasets"
  ],
  "architecture_style": "Monolithic training and evaluation scripts with modular reusable ML utility library components",
  "deployment_signals": [
    "TensorBoard logging and checkpointing",
    "ONNX model export for portable inference",
    "Structured configuration and artifact directories"
  ],
  "ai_capabilities": [
    "Optical character recognition (OCR) for CAPTCHA images",
    "Sequence modeling with BLSTM layers",
    "CTC-based decoding via ctc_decoder"
  ],
  "data_sources": [
    "Local CAPTCHA image datasets in Datasets/captcha-images-v3",
    "CSV-based splits for training, validation, and test data"
  ],
  "notable_strengths": [
    "Clear separation between task-specific scripts and reusable ML tooling (mltu)",
    "Use of standard OCR architecture and training practices",
    "Inclusion of ONNX for deployment flexibility",
    "Good experiment organization via timestamped directories and config persistence"
  ],
  "limitations": [
    "No top-level requirements or environment file for the whole project",
    "Hard-coded absolute paths in evaluation script reduce portability",
    "No production API or UI for serving predictions",
    "No automated tests or CI configuration"
  ],
  "confidence": "high"
}
```

