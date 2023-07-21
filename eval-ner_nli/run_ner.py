# Evaluate NER script.
# The script is modified from transformers module from HuggingFace.
# Copyright (c) 2023 Robert Bosch GmbH
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import datasets
import numpy as np
from datasets import ClassLabel, load_dataset, load_metric

import transformers
import transformers.adapters.composition as ac
from transformers import (
    AdapterConfig,
    AdapterTrainer,
    AutoConfig,
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    HfArgumentParser,
    MultiLingAdapterArguments,
    PreTrainedTokenizerFast,
    Trainer,
    TrainingArguments,
    set_seed,
)
#from trainer_self import Trainer
from transformers.trainer_utils import get_last_checkpoint
from transformers.utils import check_min_version
from transformers.utils.versions import require_version
from meta_model import BertEmbed, BertMetaEmbed, BertMetaDomainEmbed

# Will error if the minimal version of Transformers is not installed. Remove at your own risks.
check_min_version("4.11.0")

require_version("datasets>=1.8.0", "To fix: pip install -r examples/pytorch/token-classification/requirements.txt")

logger = logging.getLogger(__name__)


@dataclass
class ModelArguments:
    """
    Arguments pertaining to which model/config/tokenizer we are going to fine-tune from.
    """

    model_name_or_path: str = field(
        metadata={"help": "Path to pretrained model or model identifier from huggingface.co/models"}
    )
    config_name: Optional[str] = field(
        default=None, metadata={"help": "Pretrained config name or path if not the same as model_name"}
    )
    tokenizer_name: Optional[str] = field(
        default=None, metadata={"help": "Pretrained tokenizer name or path if not the same as model_name"}
    )
    cache_dir: Optional[str] = field(
        default=None,
        metadata={"help": "Where do you want to store the pretrained models downloaded from huggingface.co"},
    )
    model_revision: str = field(
        default="main",
        metadata={"help": "The specific model version to use (can be a branch name, tag name or commit id)."},
    )
    use_auth_token: bool = field(
        default=False,
        metadata={
            "help": "Will use the token generated when running `transformers-cli login` (necessary to use this script "
            "with private models)."
        },
    )
    use_metaemb: bool = field(
        default=False,
        metadata={
            "help": "Whether to use the meta embedding."
        },
    )
    use_domain_metaemb: bool = field(
        default=False,
        metadata={
            "help": "Whether to use the domain meta embedding."
        },
    )
    use_average: bool = field(
        default=True,
        metadata={
            "help": "Meta Embedding method: average."
        },
    )
    use_attention: bool = field(
        default=False,
        metadata={
            "help": "Meta Embedding method: attention."
        },
    )
    ignore_tod: bool = field(
        default=False,
        metadata={
            "help": "Whether to ignore BERT."
        },
    )
    method: str = field(
        default="subword",
        metadata={
            "help": "Which subword aggregation method to use: subword, whitespace"
        },
    )
    model_name_or_path_2: str = field(
        default=None, metadata={"help": "Path to pretrained model or model identifier from huggingface.co/models"}
    )
    model_name_or_path_3: str = field(
        default=None, metadata={"help": "Path to pretrained model or model identifier from huggingface.co/models"}
    )
    model_name_or_path_4: str = field(
        default=None, metadata={"help": "Path to pretrained model or model identifier from huggingface.co/models"}
    )
    model_name_or_path_5: str = field(
        default=None, metadata={"help": "Path to pretrained model or model identifier from huggingface.co/models"}
    )
    model_name_or_path_6: str = field(
        default=None, metadata={"help": "Path to pretrained model or model identifier from huggingface.co/models"}
    )

@dataclass
class DataTrainingArguments:
    """
    Arguments pertaining to what data we are going to input our model for training and eval.
    """

    task_name: Optional[str] = field(default="ner", metadata={"help": "The name of the task (ner, pos...)."})
    dataset_name: Optional[str] = field(
        default=None, metadata={"help": "The name of the dataset to use (via the datasets library)."}
    )
    dataset_config_name: Optional[str] = field(
        default=None, metadata={"help": "The configuration name of the dataset to use (via the datasets library)."}
    )
    train_file: Optional[str] = field(
        default=None, metadata={"help": "The input training data file (a csv or JSON file)."}
    )
    validation_file: Optional[str] = field(
        default=None,
        metadata={"help": "An optional input evaluation data file to evaluate on (a csv or JSON file)."},
    )
    test_file: Optional[str] = field(
        default=None,
        metadata={"help": "An optional input test data file to predict on (a csv or JSON file)."},
    )
    text_column_name: Optional[str] = field(
        default=None, metadata={"help": "The column name of text to input in the file (a csv or JSON file)."}
    )
    label_column_name: Optional[str] = field(
        default=None, metadata={"help": "The column name of label to input in the file (a csv or JSON file)."}
    )
    overwrite_cache: bool = field(
        default=False, metadata={"help": "Overwrite the cached training and evaluation sets"}
    )
    preprocessing_num_workers: Optional[int] = field(
        default=None,
        metadata={"help": "The number of processes to use for the preprocessing."},
    )
    max_seq_length: int = field(
        default=None,
        metadata={
            "help": "The maximum total input sequence length after tokenization. If set, sequences longer "
            "than this will be truncated, sequences shorter will be padded."
        },
    )
    pad_to_max_length: bool = field(
        default=False,
        metadata={
            "help": "Whether to pad all samples to model maximum sentence length. "
            "If False, will pad the samples dynamically when batching to the maximum length in the batch. More "
            "efficient on GPU but very bad for TPU."
        },
    )
    max_train_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": "For debugging purposes or quicker training, truncate the number of training examples to this "
            "value if set."
        },
    )
    max_eval_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": "For debugging purposes or quicker training, truncate the number of evaluation examples to this "
            "value if set."
        },
    )
    max_predict_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": "For debugging purposes or quicker training, truncate the number of prediction examples to this "
            "value if set."
        },
    )
    label_all_tokens: bool = field(
        default=False,
        metadata={
            "help": "Whether to put the label for one word on all tokens of generated by that word or just on the "
            "one (in which case the other tokens will have a padding index)."
        },
    )
    return_entity_level_metrics: bool = field(
        default=False,
        metadata={"help": "Whether to return all the entity levels during evaluation or just the overall ones."},
    )

    def __post_init__(self):
        if self.dataset_name is None and self.train_file is None and self.validation_file is None:
            raise ValueError("Need either a dataset name or a training/validation file.")
        else:
            if self.train_file is not None:
                extension = self.train_file.split(".")[-1]
                assert extension in ["csv", "json"], "`train_file` should be a csv or a json file."
            if self.validation_file is not None:
                extension = self.validation_file.split(".")[-1]
                assert extension in ["csv", "json"], "`validation_file` should be a csv or a json file."
        self.task_name = self.task_name.lower()


def main():
    # See all possible arguments in src/transformers/training_args.py
    # or by passing the --help flag to this script.
    # We now keep distinct sets of args, for a cleaner separation of concerns.

    parser = HfArgumentParser((ModelArguments, DataTrainingArguments, TrainingArguments, MultiLingAdapterArguments))
    if len(sys.argv) == 2 and sys.argv[1].endswith(".json"):
        # If we pass only one argument to the script and it's the path to a json file,
        # let's parse it to get our arguments.
        model_args, data_args, training_args, adapter_args = parser.parse_json_file(
            json_file=os.path.abspath(sys.argv[1])
        )
    else:
        model_args, data_args, training_args, adapter_args = parser.parse_args_into_dataclasses()

    # Setup logging
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    log_level = training_args.get_process_log_level()
    logger.setLevel(log_level)
    datasets.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.enable_default_handler()
    transformers.utils.logging.enable_explicit_format()

    # Log on each process the small summary:
    logger.warning(
        f"Process rank: {training_args.local_rank}, device: {training_args.device}, n_gpu: {training_args.n_gpu}"
        + f"distributed training: {bool(training_args.local_rank != -1)}, 16-bits training: {training_args.fp16}"
    )
    logger.info(f"Training/evaluation parameters {training_args}")

    # Detecting last checkpoint.
    last_checkpoint = None
    if os.path.isdir(training_args.output_dir) and training_args.do_train and not training_args.overwrite_output_dir:
        last_checkpoint = get_last_checkpoint(training_args.output_dir)
        if last_checkpoint is None and len(os.listdir(training_args.output_dir)) > 0:
            raise ValueError(
                f"Output directory ({training_args.output_dir}) already exists and is not empty. "
                "Use --overwrite_output_dir to overcome."
            )
        elif last_checkpoint is not None and training_args.resume_from_checkpoint is None:
            logger.info(
                f"Checkpoint detected, resuming training at {last_checkpoint}. To avoid this behavior, change "
                "the `--output_dir` or add `--overwrite_output_dir` to train from scratch."
            )

    # Set seed before initializing model.
    set_seed(training_args.seed)
    #set_seed(20)

    # Get the datasets: you can either provide your own CSV/JSON/TXT training and evaluation files (see below)
    # or just provide the name of one of the public datasets available on the hub at https://huggingface.co/datasets/
    # (the dataset will be downloaded automatically from the datasets Hub).
    #
    # For CSV/JSON files, this script will use the column called 'text' or the first column if no column called
    # 'text' is found. You can easily tweak this behavior (see below).
    #
    # In distributed training, the load_dataset function guarantee that only one local process can concurrently
    # download the dataset.
    if data_args.dataset_name is not None:
        # Downloading and loading a dataset from the hub.
        raw_datasets = load_dataset(
            data_args.dataset_name, data_args.dataset_config_name, cache_dir=model_args.cache_dir
        )
    else:
        data_files = {}
        if data_args.train_file is not None:
            data_files["train"] = data_args.train_file
        if data_args.validation_file is not None:
            data_files["validation"] = data_args.validation_file
        if data_args.test_file is not None:
            data_files["test"] = data_args.test_file
        extension = data_args.train_file.split(".")[-1]
        raw_datasets = load_dataset(extension, data_files=data_files, cache_dir=model_args.cache_dir)
    # See more about loading any type of standard or custom dataset (from files, python dict, pandas DataFrame, etc) at
    # https://huggingface.co/docs/datasets/loading_datasets.html.
    print(raw_datasets)
    if training_args.do_train:
        column_names = raw_datasets["train"].column_names
        features = raw_datasets["train"].features
    else:
        column_names = raw_datasets["validation"].column_names
        features = raw_datasets["validation"].features

    if data_args.text_column_name is not None:
        text_column_name = data_args.text_column_name
    elif "tokens" in column_names:
        text_column_name = "tokens"
    else:
        text_column_name = column_names[0]

    if data_args.label_column_name is not None:
        label_column_name = data_args.label_column_name
    elif f"{data_args.task_name}_tags" in column_names:
        label_column_name = f"{data_args.task_name}_tags"
    else:
        label_column_name = column_names[1]

    # In the event the labels are not a `Sequence[ClassLabel]`, we will need to go through the dataset to get the
    # unique labels.
    def get_label_list(labels):
        unique_labels = set()
        for label in labels:
            unique_labels = unique_labels | set(label)
        label_list = list(unique_labels)
        label_list.sort()
        return label_list

    if isinstance(features[label_column_name].feature, ClassLabel):
        label_list = features[label_column_name].feature.names
        # No need to convert the labels since they are already ints.
        label_to_id = {i: i for i in range(len(label_list))}
    else:
        label_list = get_label_list(raw_datasets["train"][label_column_name])
        label_to_id = {l: i for i, l in enumerate(label_list)}
    num_labels = len(label_list)
    
    print(label_list)
    # Load pretrained model and tokenizer
    #
    # Distributed training:
    # The .from_pretrained methods guarantee that only one local process can concurrently
    # download model & vocab.
    config = AutoConfig.from_pretrained(
        model_args.config_name if model_args.config_name else model_args.model_name_or_path,
        num_labels=num_labels,
        label2id=label_to_id,
        id2label={i: l for l, i in label_to_id.items()},
        finetuning_task=data_args.task_name,
        cache_dir=model_args.cache_dir,
        revision=model_args.model_revision,
        use_auth_token=True if model_args.use_auth_token else None,
    )

    tokenizer_name_or_path = model_args.tokenizer_name if model_args.tokenizer_name else model_args.model_name_or_path
    if config.model_type in {"gpt2", "roberta"}:
        tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_name_or_path,
            cache_dir=model_args.cache_dir,
            use_fast=True,
            revision=model_args.model_revision,
            use_auth_token=True if model_args.use_auth_token else None,
            add_prefix_space=True,
        )
    else:
        if "financial/BERT_MLM_EMB_ONLY_TOKENIZER" in tokenizer_name_or_path:
            print("Load financial tokenizer")
            tokenizer_name_or_path = "./cache/transformer/tokenizer/background-x/bert-base-uncased/financial"
            tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_name_or_path,
                cache_dir=model_args.cache_dir,
                use_fast=True,
                revision=model_args.model_revision,
                use_auth_token=True if model_args.use_auth_token else None,
            )
            print(len(tokenizer.vocab))
            with open(tokenizer_name_or_path+"/vocab_new.txt") as file:
                new_vocab = [line.rstrip() for line in file]
            tokenizer.add_tokens(new_vocab)
            print(len(tokenizer.vocab))
        else:  
            tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_name_or_path,
                cache_dir=model_args.cache_dir,
                use_fast=True,
                revision=model_args.model_revision,
                use_auth_token=True if model_args.use_auth_token else None,
            )

    model = AutoModelForTokenClassification.from_pretrained(
        model_args.model_name_or_path,
        from_tf=bool(".ckpt" in model_args.model_name_or_path),
        config=config,
        cache_dir=model_args.cache_dir,
        revision=model_args.model_revision,
        use_auth_token=True if model_args.use_auth_token else None,
    )
    if model_args.use_metaemb:
        embedding_1 = BertEmbed.from_pretrained(model_args.model_name_or_path, cache_dir = model_args.cache_dir) #bert
        embedding_2 = BertEmbed.from_pretrained(model_args.model_name_or_path_2, cache_dir = model_args.cache_dir) #bert-MLMEMB-SAMEDOMAIN
        embedding_3 = None if model_args.model_name_or_path_3==None else BertEmbed.from_pretrained(model_args.model_name_or_path_3, cache_dir = model_args.cache_dir) #bert-MLMEMB--OTHERDOMAIN
        embedding_4 = None if model_args.model_name_or_path_4==None else BertEmbed.from_pretrained(model_args.model_name_or_path_4, cache_dir = model_args.cache_dir) #bert-MLMEMB--OTHERDOMAIN
        embedding_5 = None if model_args.model_name_or_path_5==None else BertEmbed.from_pretrained(model_args.model_name_or_path_5, cache_dir = model_args.cache_dir) #bert-MLMEMB--OTHERDOMAIN
        embedding_6 = None if model_args.model_name_or_path_6==None else BertEmbed.from_pretrained(model_args.model_name_or_path_6, cache_dir = model_args.cache_dir) #bert-MLMEMB--OTHERDOMAIN
        print("embedding 1: {}".format(model_args.model_name_or_path))
        print("embedding 2: {}".format(model_args.model_name_or_path_2))
        print("embedding 3: {}".format(model_args.model_name_or_path_3))
        print("embedding 4: {}".format(model_args.model_name_or_path_4))
        print("embedding 5: {}".format(model_args.model_name_or_path_5))
        print("embedding 6: {}".format(model_args.model_name_or_path_6))
        model.bert.embeddings = BertMetaEmbed(config = model.config, 
                                              embedding_1 = embedding_1, 
                                              embedding_2 = embedding_2,
                                              embedding_3 = embedding_3,
                                              embedding_4 = embedding_4,
                                              embedding_5 = embedding_5,
                                              embedding_6 = embedding_6,
                                              use_average = True if model_args.use_average else False,
                                              use_attention = True if model_args.use_attention else False,
                                              ignore_tod = True if model_args.ignore_tod else False
                                              )
        print("Use Attention: {}".format(model.bert.embeddings.use_attention))
        print("Use Average: {}".format(model.bert.embeddings.use_average))
        print("Ignore BERT: {}".format(model.bert.embeddings.ignore_tod))
        for param in model.bert.named_parameters():
            if "embedding_" in param[0]:
                param[1].requires_grad=False
        for param in model.bert.named_parameters():
            print("Param: {} Requires_grad: {}".format(param[0], param[1].requires_grad))
        print(model)
        
    elif model_args.use_domain_metaemb:
        embedding_1 = BertEmbed.from_pretrained(model_args.model_name_or_path, cache_dir = model_args.cache_dir) #bert
        embedding_2 = BertEmbed.from_pretrained(model_args.model_name_or_path_2, cache_dir = model_args.cache_dir) #bert-MLMEMB-SAMEDOMAIN
        embedding_3 = None if model_args.model_name_or_path_3==None else BertEmbed.from_pretrained(model_args.model_name_or_path_3, cache_dir = model_args.cache_dir) #bert-MLMEMB--OTHERDOMAIN
        embedding_4 = None if model_args.model_name_or_path_4==None else BertEmbed.from_pretrained(model_args.model_name_or_path_4, cache_dir = model_args.cache_dir) #bert-MLMEMB--OTHERDOMAIN
        embedding_5 = None if model_args.model_name_or_path_5==None else BertEmbed.from_pretrained(model_args.model_name_or_path_5, cache_dir = model_args.cache_dir) #bert-MLMEMB--OTHERDOMAIN
        embedding_6 = None if model_args.model_name_or_path_6==None else BertEmbed.from_pretrained(model_args.model_name_or_path_6, cache_dir = model_args.cache_dir) #bert-MLMEMB--OTHERDOMAIN

        tokenizer_1 = AutoTokenizer.from_pretrained(model_args.model_name_or_path, cache_dir = model_args.cache_dir)
        if "financial/BERT_MLM_EMB_ONLY_TOKENIZER" in model_args.model_name_or_path_2:
            print("Load financial tokenizer")
            tokenizer_name_or_path = "./cache/transformer/tokenizer/background-x/bert-base-uncased/financial"
            tokenizer_2 = AutoTokenizer.from_pretrained(
                tokenizer_name_or_path,
                cache_dir=model_args.cache_dir,
                use_fast=True,
                revision=model_args.model_revision,
                use_auth_token=True if model_args.use_auth_token else None,
            )
            print(len(tokenizer.vocab))
            with open(tokenizer_name_or_path+"/vocab_new.txt") as file:
                new_vocab = [line.rstrip() for line in file]
            tokenizer.add_tokens(new_vocab)
            print(len(tokenizer.vocab))
        else:
            tokenizer_2 = AutoTokenizer.from_pretrained(model_args.model_name_or_path_2, cache_dir = model_args.cache_dir)
        tokenizer_3 = None if model_args.model_name_or_path_3==None else AutoTokenizer.from_pretrained(model_args.model_name_or_path_3, cache_dir = model_args.cache_dir)
        tokenizer_4 = None if model_args.model_name_or_path_4==None else AutoTokenizer.from_pretrained(model_args.model_name_or_path_4, cache_dir = model_args.cache_dir)
        tokenizer_5 = None if model_args.model_name_or_path_5==None else AutoTokenizer.from_pretrained(model_args.model_name_or_path_5, cache_dir = model_args.cache_dir)
        tokenizer_6 = None if model_args.model_name_or_path_6==None else AutoTokenizer.from_pretrained(model_args.model_name_or_path_6, cache_dir = model_args.cache_dir)
        
        print("embedding/tokenizer 1: {}".format(model_args.model_name_or_path))
        print("embedding/tokenizer 2: {}".format(model_args.model_name_or_path_2))
        print("embedding/tokenizer 3: {}".format(model_args.model_name_or_path_3))
        print("embedding/tokenizer 4: {}".format(model_args.model_name_or_path_4))
        print("embedding/tokenizer 5: {}".format(model_args.model_name_or_path_5))
        print("embedding/tokenizer 6: {}".format(model_args.model_name_or_path_6))
        model.bert.embeddings = BertMetaDomainEmbed(config = model.config, 
                                                    embedding_1 = embedding_1, 
                                                    embedding_2 = embedding_2,
                                                    embedding_3 = embedding_3,
                                                    embedding_4 = embedding_4, 
                                                    embedding_5 = embedding_5,
                                                    embedding_6 = embedding_6,
                                                    tokenizer_1 = tokenizer_1,
                                                    tokenizer_2 = tokenizer_2,
                                                    tokenizer_3 = tokenizer_3,
                                                    tokenizer_4 = tokenizer_4,
                                                    tokenizer_5 = tokenizer_5,
                                                    tokenizer_6 = tokenizer_6,
                                                    method = model_args.method,
                                                    use_average = True if model_args.use_average else False,
                                                    use_attention = True if model_args.use_attention else False,
                                                    ignore_tod = True if model_args.ignore_tod else False
                                                    )
        print("Subword aggregation method: {}".format(model.bert.embeddings.method))
        print("Use Attention: {}".format(model.bert.embeddings.use_attention))
        print("Use Average: {}".format(model.bert.embeddings.use_average))
        print("Ignore BERT: {}".format(model.bert.embeddings.ignore_tod))
        for param in model.bert.named_parameters():
            if "embedding_" in param[0]:
                param[1].requires_grad=False
        for param in model.bert.named_parameters():
            print("Param: {} Requires_grad: {}".format(param[0], param[1].requires_grad))
        print(model)
        

    # Setup adapters
    if adapter_args.train_adapter:
        task_name = data_args.dataset_name or "ner"
        # check if adapter already exists, otherwise add it
        if task_name not in model.config.adapters:
            # resolve the adapter config
            adapter_config = AdapterConfig.load(
                adapter_args.adapter_config,
                non_linearity=adapter_args.adapter_non_linearity,
                reduction_factor=adapter_args.adapter_reduction_factor,
            )
            # load a pre-trained from Hub if specified
            if adapter_args.load_adapter:
                print("Load Adapter", adapter_args.load_adapter)
                print("Adapter Config", adapter_config)
                print("Task", task_name)
                model.load_adapter(
                    adapter_args.load_adapter,
                    config=adapter_config,
                    load_as=task_name,
                )
            # otherwise, add a fresh adapter
            else:
                model.add_adapter(task_name, config=adapter_config)
                print("Add adapter")
            
        # optionally load a pre-trained language adapter
        if adapter_args.load_lang_adapter:
            # resolve the language adapter config
            lang_adapter_config = AdapterConfig.load(
                adapter_args.lang_adapter_config,
                non_linearity=adapter_args.lang_adapter_non_linearity,
                reduction_factor=adapter_args.lang_adapter_reduction_factor,
            )
            # load the language adapter from Hub
            lang_adapter_name = model.load_adapter(
                adapter_args.load_lang_adapter,
                config=lang_adapter_config,
                load_as=adapter_args.language,
            )
        else:
            lang_adapter_name = None
        # Freeze all model weights except of those of this adapter
        model.train_adapter([task_name])
        # Set the adapters to be used in every forward pass
        if lang_adapter_name:
            model.set_active_adapters(ac.Stack(lang_adapter_name, task_name))
        else:
            model.set_active_adapters([task_name])
    else:
        if adapter_args.load_adapter or adapter_args.load_lang_adapter:
            raise ValueError(
                "Adapters can only be loaded in adapters training mode."
                "Use --train_adapter to enable adapter training"
            )
    print(model)
    
    # Tokenizer check: this script requires a fast tokenizer.
    if not isinstance(tokenizer, PreTrainedTokenizerFast):
        raise ValueError(
            "This example script only works for models that have a fast tokenizer. Checkout the big table of models "
            "at https://huggingface.co/transformers/index.html#supported-frameworks to find the model types that meet this "
            "requirement"
        )

    # Preprocessing the dataset
    # Padding strategy
    padding = "max_length" if data_args.pad_to_max_length else False
    print(data_args.max_seq_length)
    # Tokenize all texts and align the labels with them.
    def tokenize_and_align_labels(examples):
        tokenized_inputs = tokenizer(
            examples[text_column_name],
            padding=padding,
            truncation=True,
            max_length=data_args.max_seq_length,
            # We use this argument because the texts in our dataset are lists of words (with a label for each word).
            is_split_into_words=True,
            #return_offsets_mapping = True
        )
        labels = []
        for i, label in enumerate(examples[label_column_name]):
            word_ids = tokenized_inputs.word_ids(batch_index=i)
            previous_word_idx = None
            label_ids = []
            for word_idx in word_ids:
                # Special tokens have a word id that is None. We set the label to -100 so they are automatically
                # ignored in the loss function.
                if word_idx is None:
                    label_ids.append(-100)
                # We set the label for the first token of each word.
                elif word_idx != previous_word_idx:
                    label_ids.append(label_to_id[label[word_idx]])
                # For the other tokens in a word, we set the label to either the current label or -100, depending on
                # the label_all_tokens flag.
                else:
                    label_ids.append(label_to_id[label[word_idx]] if data_args.label_all_tokens else -100)
                previous_word_idx = word_idx
            labels.append(label_ids)
        # offsets_start = []
        # offsets_end = []
        # if "offset_mapping" in tokenized_inputs.keys():
        #     for k in tokenized_inputs["offset_mapping"]:
        #         start = [item[0] for item in k] #list(sum(k, ())) #[tuple(item) for item in k]
        #         offsets_start.append(start)
        #         end = [item[1] for item in k] #list(sum(k, ())) #[tuple(item) for item in k]
        #         offsets_end.append(end)
        # tokenized_inputs["offset_mapping_start"] = offsets_start
        # tokenized_inputs["offset_mapping_end"] = offsets_end
        tokenized_inputs["labels"] = labels
        return tokenized_inputs

    if training_args.do_train:
        if "train" not in raw_datasets:
            raise ValueError("--do_train requires a train dataset")
        train_dataset = raw_datasets["train"]
        if data_args.max_train_samples is not None:
            train_dataset = train_dataset.select(range(data_args.max_train_samples))
        with training_args.main_process_first(desc="train dataset map pre-processing"):
            train_dataset = train_dataset.map(
                tokenize_and_align_labels,
                batched=True,
                num_proc=data_args.preprocessing_num_workers,
                load_from_cache_file=not data_args.overwrite_cache,
                desc="Running tokenizer on train dataset",
            )

    if training_args.do_eval:
        if "validation" not in raw_datasets:
            raise ValueError("--do_eval requires a validation dataset")
        eval_dataset = raw_datasets["validation"]
        if data_args.max_eval_samples is not None:
            eval_dataset = eval_dataset.select(range(data_args.max_eval_samples))
        with training_args.main_process_first(desc="validation dataset map pre-processing"):
            eval_dataset = eval_dataset.map(
                tokenize_and_align_labels,
                batched=True,
                num_proc=data_args.preprocessing_num_workers,
                load_from_cache_file=not data_args.overwrite_cache,
                desc="Running tokenizer on validation dataset",
            )

    if training_args.do_predict:
        if "test" not in raw_datasets:
            raise ValueError("--do_predict requires a test dataset")
        predict_dataset = raw_datasets["test"]
        if data_args.max_predict_samples is not None:
            predict_dataset = predict_dataset.select(range(data_args.max_predict_samples))
        with training_args.main_process_first(desc="prediction dataset map pre-processing"):
            predict_dataset = predict_dataset.map(
                tokenize_and_align_labels,
                batched=True,
                num_proc=data_args.preprocessing_num_workers,
                load_from_cache_file=not data_args.overwrite_cache,
                desc="Running tokenizer on prediction dataset",
            )

    # Data collator
    data_collator = DataCollatorForTokenClassification(tokenizer, pad_to_multiple_of=8 if training_args.fp16 else None)

    # Metrics
    metric = load_metric("./metrics/seqeval")

    def compute_metrics(p):
        predictions, labels = p
        predictions = np.argmax(predictions, axis=2)

        # Remove ignored index (special tokens)
        true_predictions = [
            [label_list[p] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]
        true_labels = [
            [label_list[l] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]
        results = metric.compute(predictions=true_predictions, references=true_labels)
        if data_args.return_entity_level_metrics:
            # Unpack nested dictionaries
            final_results = {}
            for key, value in results.items():
                if isinstance(value, dict):
                    for n, v in value.items():
                        final_results[f"{key}_{n}"] = v
                else:
                    final_results[key] = value
            return final_results
        else:
            return {
                "precision": results["overall_precision"],
                "recall": results["overall_recall"],
                "f1": results["overall_f1"],
                "accuracy": results["overall_accuracy"],
            }

    # Initialize our Trainer
    trainer_class = AdapterTrainer if adapter_args.train_adapter else Trainer
    trainer = trainer_class(
        model=model,
        args=training_args,
        train_dataset=train_dataset if training_args.do_train else None,
        eval_dataset=eval_dataset if training_args.do_eval else None,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    # Training
    if training_args.do_train:
        checkpoint = None
        if training_args.resume_from_checkpoint is not None:
            checkpoint = training_args.resume_from_checkpoint
        elif last_checkpoint is not None:
            checkpoint = last_checkpoint
        train_result = trainer.train(resume_from_checkpoint=checkpoint)
        metrics = train_result.metrics
        trainer.save_model()  # Saves the tokenizer too for easy upload

        max_train_samples = (
            data_args.max_train_samples if data_args.max_train_samples is not None else len(train_dataset)
        )
        metrics["train_samples"] = min(max_train_samples, len(train_dataset))

        trainer.log_metrics("train", metrics)
        trainer.save_metrics("train", metrics)
        trainer.save_state()

    # Evaluation
    if training_args.do_eval:
        logger.info("*** Evaluate ***")

        metrics = trainer.evaluate()

        max_eval_samples = data_args.max_eval_samples if data_args.max_eval_samples is not None else len(eval_dataset)
        metrics["eval_samples"] = min(max_eval_samples, len(eval_dataset))

        trainer.log_metrics("eval", metrics)
        trainer.save_metrics("eval", metrics)

    # Predict
    if training_args.do_predict:
        logger.info("*** Predict ***")

        predictions, labels, metrics = trainer.predict(predict_dataset, metric_key_prefix="predict")
        predictions = np.argmax(predictions, axis=2)

        # Remove ignored index (special tokens)
        true_predictions = [
            [label_list[p] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]

        trainer.log_metrics("predict", metrics)
        trainer.save_metrics("predict", metrics)

        # Save predictions
        output_predictions_file = os.path.join(training_args.output_dir, "predictions.txt")
        if trainer.is_world_process_zero():
            with open(output_predictions_file, "w") as writer:
                for prediction in true_predictions:
                    writer.write(" ".join(prediction) + "\n")

    kwargs = {"finetuned_from": model_args.model_name_or_path, "tasks": "token-classification"}
    if data_args.dataset_name is not None:
        kwargs["dataset_tags"] = data_args.dataset_name
        if data_args.dataset_config_name is not None:
            kwargs["dataset_args"] = data_args.dataset_config_name
            kwargs["dataset"] = f"{data_args.dataset_name} {data_args.dataset_config_name}"
        else:
            kwargs["dataset"] = data_args.dataset_name

    # if training_args.push_to_hub:
    #     trainer.push_to_hub(**kwargs)
    # else:
    #     trainer.create_model_card(**kwargs)


def _mp_fn(index):
    # For xla_spawn (TPUs)
    main()


if __name__ == "__main__":
    main()