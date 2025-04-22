# Python Client for Omeka S API

A Python client library for interacting with the Omeka S REST API. This client provides a simple interface to access Omeka S resources with built-in pagination handling and error management.

## Features

- Easy authentication with API key support
- Automatic pagination handling
- Comprehensive error handling and logging
- Support for common Omeka S endpoints:
  - Items
  - Media
  - Item Sets (Collections)
  - Resource Templates
  - Sites
  - Resource Classes
  - Assets

## Installation

### Option 1: Install from GitHub

```bash
pip install git+https://github.com/gegedenice/omeka-s-api-client.git
```

### Option 2: Install from source

Clone this repository:

```bash
git clone https://github.com/gegedenice/omeka-s-api-client.git
cd omeka-s-api-client
```

Then install the package:

```bash
# For development installation (editable mode)
pip install -e .

# Or for regular installation
pip install .
```

## Configuration

The client accepts the following initialization parameters:

- base_url: Your Omeka S instance URL
- key_identity: API key identity (optional)
- key_credential: API key credential (optional)
- default_per_page: Default number of results per page (default: 100)

### Basic setup

```python
from omeka_s_api_client import OmekaSClient

# Initialize the client
client = OmekaSClient(
    base_url="https://your-omeka-instance.org",
    key_identity="your-key-identity",
    key_credential="your-key-credential"
)
```

### Error Handling

The client includes a custom OmekaSClientError exception class for error handling:

```python
try:
    item = client.get_item(999999)  # Non-existent item
except OmekaSClientError as e:
    print(f"API Error: {e}")
```

### Logging

The client uses Python's built-in logging module. To adjust the log level:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)  # For detailed logging
```

## Usage

See examples in notebooks folder.
