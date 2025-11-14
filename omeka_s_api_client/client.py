# -*- coding: utf-8 -*-
import requests
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class OmekaSClientError(Exception):
    """Custom exception class for OmekaClient errors."""
    pass

class OmekaSClient:
    """
    A Python client for interacting with an Omeka S API.

    Handles authentication, basic requests, and pagination for common endpoints.
    Focuses on GET requests for retrieving data.
    """

    # Endpoint constants (internal mapping)
    ITEMS = "items"
    MEDIA = "media"
    ITEM_SETS = "item_sets" # Corresponds to Collections in UI
    RESOURCE_TEMPLATES = "resource_templates"
    SITES = "sites"
    RESOURCE_CLASSES = "resource_classes"
    ASSETS = "assets"
    # Add other endpoints like 'users', 'vocabularies' etc. as needed

    # Default prefixes or metadata to keep when parsing item data
    _DEFAULT_PARSE_PREFIXES = ('dcterms:', 'bibo:', 'bio:')
    _DEFAULT_PARSE_METADATA = ('dcterms:identifier','dcterms:type','dcterms:title', 'dcterms:description',
                               'dcterms:creator','dcterms:publisher','dcterms:date','dcterms:spatial',
                               'dcterms:format','dcterms:provenance','dcterms:subject','dcterms:medium',
                               'bibo:annotates','bibo:content', 'bibo:locator', 'bibo:owner')


    def __init__(self, base_url, key_identity=None, key_credential=None, default_per_page=100):
        """
        Initializes the OmekaClient.

        Args:
            base_url (str): The base URL of the Omeka S instance (e.g., "https://your-omeka.org").
            key_identity (str, optional): API key identity. Defaults to None.
            key_credential (str, optional): API key credential. Defaults to None.
            default_per_page (int): Default number of results per page for initial paginated requests.
                                   Defaults to 100.
        """
        if not base_url:
            raise ValueError("base_url cannot be empty")
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api"
        self.key_identity = key_identity
        self.key_credential = key_credential
        self.default_per_page = default_per_page
        self.headers = {
            'Accept': 'application/json',
        }
        logging.info(f"OmekaClient initialized for API: {self.api_url}")
        if key_identity:
             logging.info("Using API Key Identity.")


    def _build_params(self, **kwargs):
        """Helper to build request parameters, including API keys."""
        params = {}
        if self.key_identity:
            params['key_identity'] = self.key_identity
        if self.key_credential:
            params['key_credential'] = self.key_credential
        params.update({k: v for k, v in kwargs.items() if v is not None})
        return params

    def _request(self, method, url, params=None, **kwargs):
        """Makes an HTTP request to the Omeka S API."""
        try:
            response = requests.request(method, url, headers=self.headers, params=params, **kwargs, verify=False)
            response.raise_for_status() # Check for 4xx/5xx errors
            return response
        except requests.exceptions.RequestException as e:
            error_message = f"API request failed ({method} {url}): {e}"
            if hasattr(e, 'response') and e.response is not None:
                 try:
                    error_details = e.response.json()
                    error_message += f"\nStatus Code: {e.response.status_code}"
                    error_message += f"\nResponse: {json.dumps(error_details, indent=2)}"
                 except json.JSONDecodeError:
                    error_message += f"\nStatus Code: {e.response.status_code}"
                    error_message += f"\nResponse Text: {e.response.text[:500]}..."
            raise OmekaSClientError(error_message) from e

    # --- Generic Resource Methods ---

    def get_resource(self, api_endpoint, resource_id):
        """
        Fetches a single resource by its ID from a specified endpoint.

        Args:
            api_endpoint (str): The API endpoint name (e.g., "items", "media").
            resource_id (int or str): The unique ID of the resource.

        Returns:
            dict: The JSON representation of the resource.
        """
        url = f"{self.api_url}/{api_endpoint}/{resource_id}"
        params = self._build_params()
        logging.debug(f"Fetching single resource: GET {url}")
        response = self._request('GET', url, params=params)
        return response.json()

    def list_resources(self, api_endpoint, **kwargs):
        """
        Fetches a single page of resources from an API endpoint.

        Args:
            api_endpoint (str): The API endpoint name (e.g., "items", "media").
            **kwargs: Query parameters (page, per_page, sort_by, item_set_id, etc.).

        Returns:
            list: A list of JSON representations for the resources on the requested page.
        """
        url = f"{self.api_url}/{api_endpoint}"
        if 'per_page' not in kwargs and 'limit' not in kwargs: # Check for limit too, as Omeka often uses it
            kwargs['per_page'] = self.default_per_page
        elif 'limit' in kwargs and 'per_page' not in kwargs:
            # Treat 'limit' as 'per_page' if 'per_page' isn't explicitly set
            kwargs['per_page'] = kwargs.pop('limit')

        params = self._build_params(**kwargs)
        logging.debug(f"Listing resources (single page): GET {url} with params: {params}")
        response = self._request('GET', url, params=params)
        return response.json()

    def list_all_resources(self, api_endpoint, per_page=None, **kwargs):
        """
        Fetches ALL resources from an endpoint, handling pagination via 'Link' header.

        Args:
            api_endpoint (str): The API endpoint name (e.g., "items", "media").
            per_page (int, optional): Results per page. Defaults to client's default_per_page.
            **kwargs: Additional query parameters (e.g., item_set_id, resource_class_id).
                      'page' and 'limit' kwargs are ignored here as pagination is handled internally.

        Returns:
            list: A list containing JSON representations of ALL matching resources.
        """
        all_results = []
        page_count = 0
        effective_per_page = per_page if per_page is not None else self.default_per_page

        # Build initial parameters, removing pagination controls
        kwargs.pop('page', None)
        kwargs.pop('limit', None) # Ignore limit, as we fetch all
        current_params = self._build_params(per_page=effective_per_page, **kwargs)
        
        # Create a sanitized version of params for logging
        logging_params = {k: v for k, v in current_params.items() 
                        if k not in ('key_identity', 'key_credential')}

        current_url = f"{self.api_url}/{api_endpoint}"
        logging.info(f"Starting full fetch for endpoint '{api_endpoint}' with initial params: {kwargs}")

        while current_url:
            page_count += 1
            logging.info(f"Fetching page {page_count} from: {current_url} with params: {logging_params}")
            response = self._request('GET', current_url, params=current_params) # Pass params here
            try:
                data = response.json()
                if isinstance(data, list):
                    if not data and page_count == 1:
                        logging.info(f"No results found for endpoint '{api_endpoint}' with params: {kwargs}")
                        break
                    all_results.extend(data)
                    logging.debug(f"Fetched {len(data)} items from page {page_count}. Total: {len(all_results)}")
                else:
                    logging.warning(f"Expected list from {current_url}, got {type(data)}. Stopping.")
                    if data: all_results.append(data) # Handle edge case
                    break
            except json.JSONDecodeError as e:
                 raise OmekaSClientError(f"Failed to decode JSON from {current_url}: {e}\nResponse Text: {response.text[:500]}...")

            # --- Pagination using Link Header ---
            next_link = None
            if 'link' in response.headers:
                links = requests.utils.parse_header_links(response.headers['link'])
                for link in links:
                    if link.get('rel') == 'next':
                        next_link = link.get('url')
                        break

            if next_link:
                logging.debug(f"Found 'next' link: {next_link}")
                current_url = next_link
                # Params are in the next_link URL, so clear them for the next request call
                # The _request method will add API keys if needed.
                current_params = self._build_params() # Only keys needed now
            else:
                logging.debug("No 'next' link found. Assuming last page.")
                current_url = None # Stop loop

        logging.info(f"Finished full fetch for '{api_endpoint}'. Total resources: {len(all_results)}")
        return all_results

    # --- Convenience Methods for Common Endpoints ---

    # -- Items --
    def get_item(self, item_id):
        """Fetches a single item by ID."""
        return self.get_resource(self.ITEMS, item_id)

    def list_items(self, **kwargs):
        """Fetches a single page of items."""
        return self.list_resources(self.ITEMS, **kwargs)

    def list_all_items(self, per_page=None, **kwargs):
        """Fetches ALL items, handling pagination."""
        return self.list_all_resources(self.ITEMS, per_page=per_page, **kwargs)

    # -- Media --
    def get_media(self, media_id):
        """Fetches a single media resource by ID."""
        # Your read_media_file logic maps here
        return self.get_resource(self.MEDIA, media_id)

    def list_media(self, **kwargs):
        """Fetches a single page of media resources."""
        # Your read_media_files logic maps here (for one page)
        return self.list_resources(self.MEDIA, **kwargs)

    def list_all_media(self, per_page=None, **kwargs):
        """Fetches ALL media resources, handling pagination."""
        # Your read_media_files logic maps here (for all pages)
        return self.list_all_resources(self.MEDIA, per_page=per_page, **kwargs)

    # -- Item Sets (Collections) --
    def get_item_set(self, item_set_id):
        """Fetches a single item set (collection) by ID."""
        return self.get_resource(self.ITEM_SETS, item_set_id)

    def list_item_sets(self, **kwargs):
        """Fetches a single page of item sets (collections)."""
        return self.list_resources(self.ITEM_SETS, **kwargs)

    def list_all_item_sets(self, per_page=None, **kwargs):
        """Fetches ALL item sets (collections), handling pagination."""
        return self.list_all_resources(self.ITEM_SETS, per_page=per_page, **kwargs)

    # -- Resource Templates --
    def get_resource_template(self, template_id):
        """Fetches a single resource template by ID."""
        return self.get_resource(self.RESOURCE_TEMPLATES, template_id)

    def list_resource_templates(self, **kwargs):
        """Fetches a single page of resource templates."""
        return self.list_resources(self.RESOURCE_TEMPLATES, **kwargs)

    def list_all_resource_templates(self, per_page=None, **kwargs):
        """Fetches ALL resource templates, handling pagination."""
        return self.list_all_resources(self.RESOURCE_TEMPLATES, per_page=per_page, **kwargs)

    # -- Sites --
    def get_site(self, site_id):
        """Fetches a single site by ID."""
        return self.get_resource(self.SITES, site_id)

    def list_sites(self, **kwargs):
        """Fetches a single page of sites."""
        return self.list_resources(self.SITES, **kwargs)

    def list_all_sites(self, per_page=None, **kwargs):
        """Fetches ALL sites, handling pagination."""
        return self.list_all_resources(self.SITES, per_page=per_page, **kwargs)

    # -- Resource Classes --
    def get_resource_class(self, class_id):
        """Fetches a single resource class by ID."""
        return self.get_resource(self.RESOURCE_CLASSES, class_id)

    def list_resource_classes(self, **kwargs):
        """Fetches a single page of resource classes."""
        return self.list_resources(self.RESOURCE_CLASSES, **kwargs)

    def list_all_resource_classes(self, per_page=None, **kwargs):
        """Fetches ALL resource classes, handling pagination."""
        return self.list_all_resources(self.RESOURCE_CLASSES, per_page=per_page, **kwargs)

    # -- Assets --
    def get_asset(self, asset_name):
        """Fetches a single asset by its name (usually filename)."""
        # Note: Assets might behave slightly differently than other resources (e.g., ID vs name)
        # Adjust if needed based on API specifics for /assets/{asset_name}
        return self.get_resource(self.ASSETS, asset_name)

    def list_assets(self, **kwargs):
        """Fetches a single page of assets."""
         # Your read_omeka_assets logic maps here (for one page)
        return self.list_resources(self.ASSETS, **kwargs)

    def list_all_assets(self, per_page=None, **kwargs):
        """Fetches ALL assets, handling pagination."""
         # Your read_omeka_assets logic maps here (for all pages)
        return self.list_all_resources(self.ASSETS, per_page=per_page, **kwargs)

    # Add more convenience methods for other endpoints as needed...

    # --- NEW STATIC PARSING METHOD ---
    @staticmethod
    def digest_item_data(item_json, prefixes=None):
        """
        Parses an Omeka S item JSON-LD dictionary to extract specific fields.

        Keeps 'o:id', and fields starting with specified prefixes
        (defaulting to 'dcterms:', 'bibo:', 'bio:'). Extracts '@value'
        or 'display_title' from property value objects.

        Args:
            item_json (dict): The JSON dictionary representing a single Omeka S item.
            prefixes (tuple or list, optional): A tuple or list of namespace prefixes
                to keep (e.g., ('dcterms:', 'foaf:')) or A tuple lits of metadata
                to keep (e.g., ('dcterms:identifier','dcterms:type','dcterms:title',...)).
                Defaults to OmekaClient._DEFAULT_PARSE_PREFIXES.

        Returns:
            dict or None: A simplified dictionary containing the extracted data,
                          or None if the input item_json is not a dictionary.
                          Extracted property values are stored in lists.
        """
        if not isinstance(item_json, dict):
            logging.warning("parse_item_data received invalid input (not a dict). Returning None.")
            return None

        if prefixes is None:
            prefixes = OmekaSClient._DEFAULT_PARSE_PREFIXES

        parsed_data = {}
        if item_json.get("o:is_public") is True:
            # 1. Keep mandatory fields
            if 'o:id' in item_json:
                parsed_data['item_id'] = item_json['o:id']
            # 2. Iterate through properties and filter/extract values
            for key, property_values in item_json.items():
                # Check if the key starts with any of the desired prefixes
                if key.startswith(prefixes):
                    if not isinstance(property_values, list):
                        logging.warning(f"Expected list for property '{key}' in item {item_json.get('o:id')}, but got {type(property_values)}. Skipping.")
                        continue
                    extracted_values = []
                    for value_object in property_values:
                        if not isinstance(value_object, dict):
                            logging.warning(f"Expected dict within list for property '{key}' in item {item_json.get('o:id')}, but got {type(value_object)}. Skipping this value.")
                            continue

                        value = value_object.get('@value')
                        if value is None:
                            # Fallback to display_title if @value is not present
                            value = value_object.get('display_title')

                        # Add the extracted value if we found one
                        if value is not None:
                            extracted_values.append(value)
                        # else:
                            # Optional: Log if neither @value nor display_title was found for a value object
                            # logging.debug(f"Property '{key}', item {item_json.get('o:id')}: No '@value' or 'display_title' in object: {value_object}"

                    # Only add the property to the result if we extracted at least one value
                    if extracted_values:
                        cleaned_key = key.split(":")[1].strip().capitalize() # remove the vocabulary prefix in key label and capitalize
                        parsed_data[cleaned_key] = "|".join(extracted_values)
        return parsed_data

# --- Helper function (needed for the workflow example) ---
def flatten_list(list_of_lists):
    """Flattens a list of lists into a single list."""
    return [item for sublist in list_of_lists for item in sublist]