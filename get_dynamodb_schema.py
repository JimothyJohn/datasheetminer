#!/usr/bin/env python3
"""
Script to extract schema from DynamoDB table 'gearbox_catalog' and write to schema.json
"""

import boto3
import json
from typing import Dict, Any, Set
from decimal import Decimal


def get_dynamodb_schema(table_name: str) -> Dict[str, Any]:
    """
    Extract schema from a DynamoDB table by scanning items and analyzing their structure.
    
    Args:
        table_name: Name of the DynamoDB table
        
    Returns:
        Dictionary containing the schema information
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    schema = {
        'table_name': table_name,
        'attributes': {},
        'key_schema': [],
        'sample_count': 0
    }
    
    # Get table metadata
    table_info = table.meta.client.describe_table(TableName=table_name)
    table_desc = table_info['Table']
    
    # Extract key schema
    schema['key_schema'] = table_desc.get('KeySchema', [])
    
    # Track all seen attributes and their types
    all_attributes = {}
    
    try:
        # Scan table to analyze item structure
        response = table.scan()
        items = response['Items']
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])
        
        schema['sample_count'] = len(items)
        
        # Analyze each item to build schema
        for item in items:
            for attr_name, attr_value in item.items():
                attr_type = get_attribute_type(attr_value)
                
                if attr_name not in all_attributes:
                    all_attributes[attr_name] = {
                        'types': set(),
                        'required': True,
                        'sample_values': []
                    }
                
                all_attributes[attr_name]['types'].add(attr_type)
                
                # Store sample values (limit to 3)
                if len(all_attributes[attr_name]['sample_values']) < 3:
                    sample_value = serialize_sample_value(attr_value)
                    if sample_value not in all_attributes[attr_name]['sample_values']:
                        all_attributes[attr_name]['sample_values'].append(sample_value)
        
        # Check which attributes are required (present in all items)
        for attr_name in all_attributes:
            required_count = sum(1 for item in items if attr_name in item)
            all_attributes[attr_name]['required'] = required_count == len(items)
            
            # Convert set to list for JSON serialization
            all_attributes[attr_name]['types'] = list(all_attributes[attr_name]['types'])
        
        schema['attributes'] = all_attributes
        
    except Exception as e:
        print(f"Error scanning table: {e}")
        schema['error'] = str(e)
    
    return schema


def get_attribute_type(value: Any) -> str:
    """
    Determine the type of a DynamoDB attribute value.
    
    Args:
        value: The attribute value
        
    Returns:
        String representing the type
    """
    if isinstance(value, str):
        return 'String'
    elif isinstance(value, (int, float, Decimal)):
        return 'Number'
    elif isinstance(value, bool):
        return 'Boolean'
    elif isinstance(value, bytes):
        return 'Binary'
    elif isinstance(value, list):
        if len(value) > 0:
            first_type = get_attribute_type(value[0])
            return f'List[{first_type}]'
        return 'List'
    elif isinstance(value, dict):
        return 'Map'
    elif isinstance(value, set):
        if len(value) > 0:
            first_item = next(iter(value))
            first_type = get_attribute_type(first_item)
            return f'Set[{first_type}]'
        return 'Set'
    else:
        return 'Unknown'


def serialize_sample_value(value: Any) -> Any:
    """
    Convert DynamoDB value to JSON-serializable format.
    
    Args:
        value: The value to serialize
        
    Returns:
        JSON-serializable representation
    """
    if isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, set):
        return list(value)
    elif isinstance(value, bytes):
        return f"<binary data: {len(value)} bytes>"
    elif isinstance(value, dict):
        return {k: serialize_sample_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [serialize_sample_value(item) for item in value[:3]]  # Limit list samples
    else:
        return value


def main():
    """Main function to extract schema and write to file."""
    table_name = 'gearbox_catalog'
    output_file = 'schema.json'
    
    print(f"Extracting schema from DynamoDB table: {table_name}")
    
    try:
        schema = get_dynamodb_schema(table_name)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
        
        print(f"Schema successfully written to {output_file}")
        print(f"Analyzed {schema.get('sample_count', 0)} items")
        print(f"Found {len(schema.get('attributes', {}))} attributes")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())