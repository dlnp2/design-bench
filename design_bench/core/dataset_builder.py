from design_bench.utils.remote_resource import RemoteResource
from typing import List, Tuple, Iterable
import abc as abc
import numpy as np
import math


class DatasetBuilder(abc.ABC):
    """An abstract base class that defines a common set of functions
    and attributes for a model-based optimization dataset, where the
    goal is to find a design 'x' that maximizes a prediction 'y':

    max_x { y = f(x) }

    Public Attributes:

    x: np.ndarray
        the design values 'x' for a model-based optimization problem
        represented as a numpy array of arbitrary type

    input_shape: Tuple[int]
        the shape of a single design values 'x', represented as a list of
        integers similar to calling np.ndarray.shape

    input_size: int
        the total number of components in the design values 'x', represented
        as a single integer, the product of its shape entries

    input_dtype: np.dtype
        the data type of the design values 'x', which is typically either
        floating point or integer (np.float32 or np.int32)

    y: np.ndarray
        the prediction values 'y' for a model-based optimization problem
        represented by a scalar floating point value per 'x'

    output_shape: Tuple[int]
        the shape of a single prediction value 'y', represented as a list of
        integers similar to calling np.ndarray.shape

    output_size: int
        the total number of components in the prediction values 'y',
        represented as a single integer, the product of its shape entries

    output_dtype: np.dtype
        the data type of the prediction values 'y', which is typically a
        type of floating point (np.float32 or np.float16)

    dataset_size: int
        the total number of paired design values 'x' and prediction values
        'y' in the dataset, represented as a single integer

    dataset_max_percentile: float
        the percentile between 0 and 100 of prediction values 'y' above
        which are hidden from access by members outside the class

    dataset_min_percentile: float
        the percentile between 0 and 100 of prediction values 'y' below
        which are hidden from access by members outside the class

    x_resources: list of RemoteResource
        a list of RemoteResource that should be downloaded before the
        dataset can be loaded and used for model-based optimization

    y_resources: list of RemoteResource
        a list of RemoteResource that should be downloaded before the
        dataset can be loaded and used for model-based optimization

    Public Methods:

    subsample(max_percentile: float,
              min_percentile: float):
        a function that exposes a subsampled version of a much larger
        model-based optimization dataset containing design values 'x'
        whose prediction values 'y' are skewed

    relabel(relabel_function:
            Callable[[np.ndarray, np.ndarray], np.ndarray]):
        a function that accepts a function that maps from a dataset of
        design values 'x' and prediction values y to a new set of
        prediction values 'y' and relabels the model-based optimization dataset

    normalize_x(new_x: np.ndarray) -> np.ndarray:
        a helper function that accepts floating point design values 'x'
        as input and standardizes them so that they have zero
        empirical mean and unit empirical variance

    denormalize_x(new_x: np.ndarray) -> np.ndarray:
        a helper function that accepts floating point design values 'x'
        as input and undoes standardization so that they have their
        original empirical mean and variance

    normalize_y(new_x: np.ndarray) -> np.ndarray:
        a helper function that accepts floating point prediction values 'y'
        as input and standardizes them so that they have zero
        empirical mean and unit empirical variance

    denormalize_y(new_x: np.ndarray) -> np.ndarray:
        a helper function that accepts floating point prediction values 'y'
        as input and undoes standardization so that they have their
        original empirical mean and variance

    map_normalize_x():
        a destructive function that standardizes the design values 'x'
        in the class dataset in-place so that they have zero empirical
        mean and unit variance

    map_denormalize_x():
        a destructive function that undoes standardization of the
        design values 'x' in the class dataset in-place which are expected
        to have zero  empirical mean and unit variance

    map_normalize_y():
        a destructive function that standardizes the prediction values 'y'
        in the class dataset in-place so that they have zero empirical
        mean and unit variance

    map_denormalize_y():
        a destructive function that undoes standardization of the
        prediction values 'y' in the class dataset in-place which are
        expected to have zero empirical mean and unit variance

    """

    @staticmethod
    @abc.abstractmethod
    def register_x_resources(**kwargs) -> List[RemoteResource]:
        """Registers a remote file for download that contains design values
        in a format compatible with the dataset builder class;
        these files are downloaded all at once in the dataset initialization

        Arguments:

        **kwargs: dict
            additional keyword arguments used for building the dataset,
            which may be domain specific and depend on whether the dataset
            contains discrete or continuous data points

        Returns:

        resources: list of RemoteResource
            a list of RemoteResource objects specific to this dataset, which
            will be automatically downloaded while the dataset is built
            and may serve as shards if the dataset is large

        """

        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def register_y_resources(**kwargs) -> List[RemoteResource]:
        """Registers a remote file for download that contains prediction
        values in a format compatible with the dataset builder class;
        these files are downloaded all at once in the dataset initialization

        Arguments:

        **kwargs: dict
            additional keyword arguments used for building the dataset,
            which may be domain specific and depend on whether the dataset
            contains discrete or continuous data points

        Returns:

        resources: list of RemoteResource
            a list of RemoteResource objects specific to this dataset, which
            will be automatically downloaded while the dataset is built
            and may serve as shards if the dataset is large

        """

        raise NotImplementedError

    def batch_transform(self, x_batch, y_batch,
                        return_x=True, return_y=True):
        """Apply a transformation to batches of samples from a model-based
        optimization data set, including sub sampling and normalization
        and potentially other used defined transformations

        Arguments:

        x_batch: np.ndarray
            a numpy array representing a batch of design values sampled
            from a model-based optimization data set
        y_batch: np.ndarray
            a numpy array representing a batch of prediction values sampled
            from a model-based optimization data set
        return_x: bool
            a boolean indicator that specifies whether the generator yields
            design values at every iteration; note that at least one of
            return_x and return_y must be set to True
        return_y: bool
            a boolean indicator that specifies whether the generator yields
            prediction values at every iteration; note that at least one
            of return_x and return_y must be set to True

        Returns:

        x_batch: np.ndarray
            a numpy array representing a batch of design values sampled
            from a model-based optimization data set
        y_batch: np.ndarray
            a numpy array representing a batch of prediction values sampled
            from a model-based optimization data set

        """

        # take a subset of the sliced arrays
        mask = np.logical_and(y_batch <= self.dataset_max_output,
                              y_batch >= self.dataset_min_output)
        indices = np.where(mask)[0]

        # sub sample the design and prediction values
        x_batch = x_batch[indices] if return_x else None
        y_batch = y_batch[indices] if return_y else None

        # normalize the design values in the batch
        if self.is_normalized_x and return_x:
            x_batch = self.normalize_x(x_batch)

        # normalize the prediction values in the batch
        if self.is_normalized_y and return_y:
            y_batch = self.normalize_y(y_batch)

        # return processed batches of designs an predictions
        return (x_batch if return_x else None,
                y_batch if return_y else None)

    def iterate_batches(self, batch_size, return_x=True,
                        return_y=True, drop_remainder=False) \
            -> Iterable[Tuple[np.ndarray, np.ndarray]]:
        """Returns an object that supports iterations, which yields tuples of
        design values 'x' and prediction values 'y' from a model-based
        optimization data set for training a model

        Arguments:

        batch_size: int
            a positive integer that specifies the batch size of samples
            taken from a model-based optimization data set; batches
            with batch_size elements are yielded
        return_x: bool
            a boolean indicator that specifies whether the generator yields
            design values at every iteration; note that at least one of
            return_x and return_y must be set to True
        return_y: bool
            a boolean indicator that specifies whether the generator yields
            prediction values at every iteration; note that at least one
            of return_x and return_y must be set to True
        drop_remainder: bool
            a boolean indicator representing whether the last batch
            should be dropped in the case it has fewer than batch_size
            elements; the default behavior is not to drop the smaller batch.

        Returns:

        generator: Iterator
            a python iterable that yields samples from a model-based
            optimization data set and returns once finished

        """

        # check whether the generator arguments are valid
        if batch_size < 1 or (not return_x and not return_y):
            raise ValueError("invalid arguments passed to batch generator")

        # prepare a list of file shards to load batches from from
        shards = [(x_resource.disk_target, y_resource.disk_target)
                  for x_resource, y_resource in
                  zip(self.x_resources, self.y_resources)]

        # track a list of incomplete batches between shards
        y_batch_size = 0
        x_batch = [] if return_x else None
        y_batch = [] if return_y else None

        # iterate through every registered shard
        num_shards = len(shards)
        for shard_id, (x_shard, y_shard) in enumerate(shards):

            # load both the design and prediction shards from the disk
            x_shard_data = np.load(x_shard) if return_x else None
            y_shard_data = np.load(y_shard)
            shard_position = 0

            # calculate the number of batches per single shard
            batch_per_shard = int(math.ceil(
                y_shard_data.shape[0] / batch_size))

            # loop once per batch contained in the shard
            for i in range(batch_per_shard):

                # how many samples will be attempted to read
                target_size = batch_size - y_batch_size

                # slice out a component of the current shard
                x_sliced = x_shard_data[shard_position:(
                    shard_position + target_size)] if return_x else None
                y_sliced = y_shard_data[shard_position:(
                    shard_position + target_size)]

                # take a subset of the sliced arrays using a pre-defined
                # transformation that sub-samples and normalizes
                x_sliced, y_sliced = self.batch_transform(
                    x_sliced, y_sliced, return_x=return_x, return_y=return_y)

                # update the read position in the shard tensor
                samples_read = (y_sliced if return_y else x_sliced).shape[0]
                shard_position += samples_read

                # update the current batch to be yielded
                y_batch_size += samples_read
                x_batch.append(x_sliced) if return_x else None
                y_batch.append(y_sliced) if return_y else None

                # yield the current batch when enough samples are loaded
                if y_batch_size >= batch_size \
                        or (not drop_remainder
                            and i + 1 == batch_per_shard
                            and shard_id + 1 == num_shards):

                    try:

                        # determine which tensors to yield
                        if return_x and return_y:
                            yield np.concatenate(x_batch, axis=0), \
                                  np.concatenate(y_batch, axis=0)
                        elif return_x:
                            yield np.concatenate(x_batch, axis=0)
                        elif return_y:
                            yield np.concatenate(y_batch, axis=0)

                    except GeneratorExit:
                        return

                    # reset the buffer for incomplete batches
                    y_batch_size = 0
                    x_batch = [] if return_x else None
                    y_batch = [] if return_y else None

    def iterate_samples(self, return_x=True, return_y=True) -> \
            Iterable[Tuple[np.ndarray, np.ndarray]]:
        """Returns an object that supports iterations, which yields tuples of
        design values 'x' and prediction values 'y' from a model-based
        optimization data set for training a model

        Arguments:

        return_x: bool
            a boolean indicator that specifies whether the generator yields
            design values at every iteration; note that at least one of
            return_x and return_y must be set to True
        return_y: bool
            a boolean indicator that specifies whether the generator yields
            prediction values at every iteration; note that at least one
            of return_x and return_y must be set to True

        Returns:

        generator: Iterator
            a python iterable that yields samples from a model-based
            optimization data set and returns once finished

        """

        # create a generator that only returns single samples
        for batch in self.iterate_batches(
                1, return_x=return_x,
                return_y=return_y, drop_remainder=False):

            # determine which tensors to yield
            if return_x and return_y:
                yield batch[0][0], batch[1][0]
            if return_x or return_y:
                yield batch[0]

    def __iter__(self):
        """Returns an object that supports iterations, which yields tuples of
        design values 'x' and prediction values 'y' from a model-based
        optimization data set for training a model

        Returns:

        generator: Iterator
            a python iterable that yields samples from a model-based
            optimization data set and returns once finished

        """

        # create a generator that returns batches of designs and predictions
        for x_batch, y_batch in self.iterate_batches(
                self.internal_batch_size, drop_remainder=False):
            yield x_batch, y_batch

    def update_x_statistics(self):
        """A helpful function that calculates the mean and standard deviation
        of the designs and predictions in a model-based optimization dataset
        either iteratively or all at once using numpy

        """

        # make sure the statistics are calculated from original samples
        original_is_normalized_x = self.is_normalized_x
        self.is_normalized_x = False

        # iterate through the entire dataset a first time
        samples = x_mean = 0
        for x_batch in self.iterate_batches(
                self.internal_batch_size,
                return_y=False, drop_remainder=False):

            # calculate how many samples are actually in the current batch
            batch_size = np.array(x_batch.shape[0], dtype=np.float32)

            # update the running mean using dynamic programming
            x_mean = x_mean * (samples / (samples + batch_size)) + \
                np.sum(x_batch,
                       axis=0, keepdims=True) / (samples + batch_size)

            # update the number of samples used in the calculation
            samples += batch_size

        # iterate through the entire dataset a second time
        samples = x_variance = 0
        for x_batch in self.iterate_batches(
                self.internal_batch_size,
                return_y=False, drop_remainder=False):

            # calculate how many samples are actually in the current batch
            batch_size = np.array(x_batch.shape[0], dtype=np.float32)

            # update the running variance using dynamic programming
            x_variance = x_variance * (samples / (samples + batch_size)) + \
                np.sum(np.square(x_batch - x_mean),
                       axis=0, keepdims=True) / (samples + batch_size)

            # update the number of samples used in the calculation
            samples += batch_size

        # expose the calculated mean and standard deviation
        self.x_mean = x_mean
        self.x_standard_dev = np.sqrt(x_variance)

        # remove zero standard deviations to prevent singularities
        self.x_standard_dev = np.where(
            self.x_standard_dev == 0.0, 1.0, self.x_standard_dev)

        # reset the normalized state to what it originally was
        self.is_normalized_x = original_is_normalized_x

    def update_y_statistics(self):
        """A helpful function that calculates the mean and standard deviation
        of the designs and predictions in a model-based optimization dataset
        either iteratively or all at once using numpy

        """

        # make sure the statistics are calculated from original samples
        original_is_normalized_y = self.is_normalized_y
        self.is_normalized_y = False

        # iterate through the entire dataset a first time
        samples = y_mean = 0
        for y_batch in self.iterate_batches(
                self.internal_batch_size,
                return_x=False, drop_remainder=False):

            # calculate how many samples are actually in the current batch
            batch_size = np.array(y_batch.shape[0], dtype=np.float32)

            # update the running mean using dynamic programming
            y_mean = y_mean * (samples / (samples + batch_size)) + \
                np.sum(y_batch,
                       axis=0, keepdims=True) / (samples + batch_size)

            # update the number of samples used in the calculation
            samples += batch_size

        # iterate through the entire dataset a second time
        samples = y_variance = 0
        for y_batch in self.iterate_batches(
                self.internal_batch_size,
                return_x=False, drop_remainder=False):

            # calculate how many samples are actually in the current batch
            batch_size = np.array(y_batch.shape[0], dtype=np.float32)

            # update the running variance using dynamic programming
            y_variance = y_variance * (samples / (samples + batch_size)) + \
                np.sum(np.square(y_batch - y_mean),
                       axis=0, keepdims=True) / (samples + batch_size)

            # update the number of samples used in the calculation
            samples += batch_size

        # expose the calculated mean and standard deviation
        self.y_mean = y_mean
        self.y_standard_dev = np.sqrt(y_variance)

        # remove zero standard deviations to prevent singularities
        self.y_standard_dev = np.where(
            self.y_standard_dev == 0.0, 1.0, self.y_standard_dev)

        # reset the normalized state to what it originally was
        self.is_normalized_y = original_is_normalized_y

    def subsample(self, max_percentile=100.0, min_percentile=0.0):
        """a function that exposes a subsampled version of a much larger
        model-based optimization dataset containing design values 'x'
        whose prediction values 'y' are skewed

        Arguments:

        max_percentile: float
            the percentile between 0 and 100 of prediction values 'y' above
            which are hidden from access by members outside the class
        min_percentile: float
            the percentile between 0 and 100 of prediction values 'y' below
            which are hidden from access by members outside the class

        """

        # return an error is the arguments are invalid
        if min_percentile > max_percentile:
            raise ValueError("invalid arguments provided")

        # remove the old sub sampling thresholds for the dataset
        self.dataset_min_percentile = 0.0
        self.dataset_max_percentile = 100.0
        self.dataset_min_output = np.NINF
        self.dataset_max_output = np.PINF

        # set the sub sampled data set to not be normalized
        original_is_normalized_x = self.is_normalized_x
        original_is_normalized_y = self.is_normalized_y
        self.is_normalized_x = False
        self.is_normalized_y = False

        # convert the original prediction generator to a numpy tensor
        y = np.concatenate(list(self.iterate_batches(
            self.internal_batch_size,
            return_x=False, drop_remainder=False)), axis=0)

        # calculate the min threshold for predictions in the dataset
        min_output = np.percentile(y[:, 0], min_percentile)
        self.dataset_min_percentile = min_percentile
        self.dataset_min_output = min_output

        # calculate the max threshold for predictions in the dataset
        max_output = np.percentile(y[:, 0], max_percentile)
        self.dataset_max_percentile = max_percentile
        self.dataset_max_output = max_output

        # create a mask for which predictions
        # in the dataset satisfy the range [min_threshold, max_threshold]
        # and update the size of the dataset based on the thresholds
        self.dataset_size = np.where(np.logical_and(
            y <= max_output, y >= min_output))[0].size

        # update normalization statistics for design values
        if original_is_normalized_x:
            self.map_normalize_x()

        # update normalization statistics for prediction values
        if original_is_normalized_y:
            self.map_normalize_y()

    @property
    def x(self) -> np.ndarray:
        """A helpful function for loading the design values from disk in case
        the dataset is set to load all at once rather than lazily and is
        overridden with a numpy array once loaded

        Returns:

        x: np.ndarray
            processed design values 'x' for a model-based optimization problem
            represented as a numpy array of arbitrary type

        """

        return np.concatenate([x for x in self.iterate_batches(
            self.internal_batch_size,
            return_y=False, drop_remainder=False)], axis=0)

    @property
    def y(self) -> np.ndarray:
        """A helpful function for loading prediction values from disk in case
        the dataset is set to load all at once rather than lazily and is
        overridden with a numpy array once loaded

        Returns:

        y: np.ndarray
            processed prediction values 'y' for a model-based optimization
            problem represented as a numpy array of arbitrary type

        """

        return np.concatenate([y for y in self.iterate_batches(
            self.internal_batch_size,
            return_x=False, drop_remainder=False)], axis=0)

    def __init__(self, internal_batch_size=32, **kwargs):
        """Initialize a model-based optimization dataset and prepare
        that dataset by loading that dataset from disk and modifying
        its distribution

        Arguments:

        internal_batch_size: int
            the number of samples per batch to use when computing
            normalization statistics of the data set and while relabeling
            the prediction values of the data set
        **kwargs: dict
            additional keyword arguments passed to the "load_dataset" method,
            which may be data specific and depend on whether the data set
            contains discrete or continuous data points

        """

        # update variables that describe the data set
        self.dataset_min_percentile = 0.0
        self.dataset_max_percentile = 100.0
        self.dataset_min_output = np.NINF
        self.dataset_max_output = np.PINF

        # initialize the normalization state to False
        self.is_normalized_x = False
        self.is_normalized_y = False

        # initialize statistics for data set normalization
        self.x_mean = None
        self.y_mean = None
        self.x_standard_dev = None
        self.y_standard_dev = None

        # pointers to remote files to be downloaded before data set use
        self.x_resources = self.register_x_resources(**kwargs)
        self.y_resources = self.register_y_resources(**kwargs)
        self.internal_batch_size = internal_batch_size

        # assert same number of x resources and y resources are provided
        if len(self.x_resources) != len(self.y_resources):
            raise ValueError("different num of x and y files not supported")

        # download the remote resources
        for file in self.x_resources + self.y_resources:
            if not file.is_downloaded:
                file.download()  # downloaded any file not present on disk

        # sample initial x and y values from the data set
        x0 = y0 = None
        self.dataset_size = 0
        for x0 in self.iterate_samples(return_y=False):
            break
        for y0 in self.iterate_samples(return_x=False):
            self.dataset_size += 1

        # check that the format of the predictions is correct
        if len(y0.shape) != 1 or y0.shape[0] != 1:
            raise ValueError(f"predictions should have shape [N, 1]:")

        # assign variables that describe the design values 'x'
        self.input_shape = x0.shape
        self.input_size = int(np.prod(x0.shape))
        self.input_dtype = x0.dtype

        # assign variables that describe the prediction values 'y'
        self.output_shape = [1]
        self.output_size = 1
        self.output_dtype = y0.dtype

    def relabel(self, relabel_function,
                shard_name="dataset_shard", shard_size=None):
        """a function that accepts a function that maps from a dataset of
        design values 'x' and prediction values y to a new set of
        prediction values 'y' and relabels a model-based optimization dataset

        Arguments:

        relabel_function: Callable[[np.ndarray, np.ndarray], np.ndarray]
            a function capable of mapping from a numpy array of design
            values 'x' and prediction values 'y' to new predictions 'y' 
            using batching to prevent memory overflow
        shard_name: str
            the string base name of the new shards to write for this dataset
            which does not contain a file extension appended to it, and
            will be written as f'{shard_name}-y-{shard_id}.npy'
        shard_size: int
            an integer specifying the intended number of training examples
            per shard in the new serialized set of prediction values;
            should be set to match the number of design values per shard

        """

        # prevent the data set for being sub-sampled
        self.dataset_min_output = np.NINF
        self.dataset_max_output = np.PINF
        num_examples = self.y.shape[0]

        # track a list of incomplete batches between shards
        new_y_resources = []
        y_shard_size = 0
        y_shard = []

        # track the number of examples and shards processed
        examples_processed = 0
        shard_id = -1

        # relabel the prediction values of the internal data set
        for x_batch, y_batch in \
                self.iterate_batches(self.internal_batch_size):

            # calculate the new prediction values to be stored as shards
            new_y_batch = relabel_function(x_batch, y_batch)
            read_position = 0

            # handle when y is already normalized
            if self.is_normalized_y:
                new_y_batch = self.denormalize_y(new_y_batch)

            # calculate the number of batches per single shard
            shard_per_batch = int(math.ceil(
                shard_size / new_y_batch.shape[0])) if shard_size else 1

            # loop once per batch contained in the shard
            for i in range(shard_per_batch):

                # calculate the intended number of samples to serialize
                target_size = shard_size - y_shard_size \
                              if shard_size else new_y_batch.shape[0]

                # slice out a component of the current shard
                y_sliced = new_y_batch[
                    read_position:read_position + target_size]

                # increment the read position in the prediction tensor
                samples_read = y_sliced.shape[0]
                read_position += samples_read

                # update the number of shards and examples processed
                examples_processed += samples_read

                # update the current shard to be serialized
                y_shard_size += samples_read
                y_shard.append(y_sliced)

                # yield the current batch when enough samples are loaded
                if y_shard_size == shard_size \
                        or (i + 1 == shard_per_batch
                            and examples_processed == num_examples):

                    # increment the total number of shards
                    shard_id += 1

                    # serialize a new resource file with the specified name
                    # and register the shard as a y resource
                    resource_file = RemoteResource(
                        f"{shard_name}-y-{shard_id}.npy",
                        is_absolute=False,
                        download_method=None, download_target=None)

                    # write the shard using numpy
                    new_y_resources.append(resource_file)
                    np.save(resource_file.disk_target,
                            np.concatenate(y_shard, axis=0))

                    # reset the buffer for incomplete batches
                    y_shard_size = 0
                    y_shard = []

        # set the resource file shards to new shard locations
        self.y_resources = new_y_resources

        # re-sample the data set and recalculate statistics
        self.subsample(max_percentile=self.dataset_max_percentile,
                       min_percentile=self.dataset_min_percentile)

    def map_normalize_x(self):
        """a function that standardizes the design values 'x' to have zero
        empirical mean and unit empirical variance in the dataset

        """

        # calculate the normalization statistics in advance
        self.update_x_statistics()

        # check design values and prediction values are not normalized
        if not self.is_normalized_x:
            self.is_normalized_x = True

    def map_normalize_y(self):
        """a function that standardizes the prediction values 'y' to have
        zero empirical mean and unit empirical variance in the dataset

        """

        # calculate the normalization statistics in advance
        self.update_y_statistics()

        # check design values and prediction values are not normalized
        if not self.is_normalized_y:
            self.is_normalized_y = True

    def normalize_x(self, x):
        """a function that standardizes the design values 'x' to have
        zero empirical mean and unit empirical variance

        Arguments:

        x: np.ndarray
            a design value represented as a numpy array potentially
            given as a batch of designs which
            shall be normalized according to dataset statistics

        Returns:

        x: np.ndarray
            a design value represented as a numpy array potentially
            given as a batch of designs which
            has been normalized using dataset statistics

        """

        # calculate the mean and standard deviation of the prediction values
        if self.x_mean is None or self.x_standard_dev is None:
            self.update_x_statistics()

        # normalize the prediction values
        return (x - self.x_mean) / self.x_standard_dev

    def normalize_y(self, y):
        """a function that standardizes the prediction values 'y' to have
        zero empirical mean and unit empirical variance

        Arguments:

        y: np.ndarray
            a prediction value represented as a numpy array potentially
            given as a batch of predictions which
            shall be normalized according to dataset statistics

        Returns:

        y: np.ndarray
            a prediction value represented as a numpy array potentially
            given as a batch of predictions which
            has been normalized using dataset statistics

        """

        # calculate the mean and standard deviation of the prediction values
        if self.y_mean is None or self.y_standard_dev is None:
            self.update_y_statistics()

        # normalize the prediction values
        return (y - self.y_mean) / self.y_standard_dev

    def map_denormalize_x(self):
        """a function that un-standardizes the design values 'x' which have
        zero empirical mean and unit empirical variance in the dataset

        """

        # check design values and prediction values are normalized
        if self.is_normalized_x:
            self.is_normalized_x = False

    def map_denormalize_y(self):
        """a function that un-standardizes the prediction values 'y' which
        have zero empirical mean and unit empirical variance in the dataset

        """

        # check design values and prediction values are normalized
        if self.is_normalized_y:
            self.is_normalized_y = False

    def denormalize_x(self, x):
        """a function that un-standardizes the design values 'x' which have
        zero empirical mean and unit empirical variance

        Arguments:

        x: np.ndarray
            a design value represented as a numpy array potentially
            given as a batch of designs which
            shall be denormalized according to dataset statistics

        Returns:

        x: np.ndarray
            a design value represented as a numpy array potentially
            given as a batch of designs which
            has been denormalized using dataset statistics

        """

        # calculate the mean and standard deviation
        if self.x_mean is None or self.x_standard_dev is None:
            self.update_x_statistics()

        # denormalize the prediction values
        return x * self.x_standard_dev + self.x_mean

    def denormalize_y(self, y):
        """a function that un-standardizes the prediction values 'y' which
        have zero empirical mean and unit empirical variance

        Arguments:

        y: np.ndarray
            a prediction value represented as a numpy array potentially
            given as a batch of predictions which
            shall be denormalized according to dataset statistics

        Returns:

        y: np.ndarray
            a prediction value represented as a numpy array potentially
            given as a batch of predictions which
            has been denormalized using dataset statistics

        """

        # calculate the mean and standard deviation
        if self.y_mean is None or self.y_standard_dev is None:
            self.update_y_statistics()

        # denormalize the prediction values
        return y * self.y_standard_dev + self.y_mean
