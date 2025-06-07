#!/usr/bin/env python3
"""
Custom task test script that writes all parameters to a text file.

Usage:
    custom_task_test.py <input_file> [--param1 value1] [--param2 value2] ...

All parameters will be written to <input_file>.txt
"""

import os
import sys
import argparse
from typing import Dict, Any
import logging

def parse_arguments():
    """Parse command line arguments dynamically."""
    # First argument is the input file
    if len(sys.argv) < 2:
        print("Error: Input file is required", file=sys.stderr)
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # Parse the remaining arguments
    parser = argparse.ArgumentParser(description='Custom task test script')
    
    # Add a dummy argument to prevent error for unknown args
    parser.add_argument('input_file', help='Input file to process')
    
    # Parse known args first to get the input file
    args, remaining_args = parser.parse_known_args()
    
    # Now parse the remaining arguments dynamically
    params = {}
    i = 0
    while i < len(remaining_args):
        arg = remaining_args[i]
        if arg.startswith('--'):
            param_name = arg[2:]  # Remove '--' prefix
            # If next argument doesn't start with '--', it's the value
            if i + 1 < len(remaining_args) and not remaining_args[i + 1].startswith('--'):
                params[param_name] = remaining_args[i + 1]
                i += 2
            else:
                # Flag parameter (no value)
                params[param_name] = True
                i += 1
        else:
            # Skip arguments that don't start with '--'
            i += 1
    
    return args.input_file, params

def write_parameters(input_file: str, params: Dict[str, Any]) -> str:
    """Write parameters to output file.
    
    Args:
        input_file: Path to the input file
        params: Dictionary of parameters
        
    Returns:
        Path to the output file
    """
    output_file = f"{input_file}.txt"
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Input file: {input_file}\n")
            f.write("=" * 40 + "\n")
            f.write("Parameters:\n")
            f.write("-" * 40 + "\n")
            
            for key, value in params.items():
                f.write(f"{key}: {value}\n")
                
        # Set file permissions to be readable by all
        os.chmod(output_file, 0o666)
        return output_file
        
    except Exception as e:
        print(f"Error writing to {output_file}: {str(e)}", file=sys.stderr)
        sys.exit(1)

def main():
    # Set up basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Parse command line arguments
    input_file, params = parse_arguments()
    
    # Log the parameters
    logging.info(f"Processing file: {input_file}")
    logging.info(f"Parameters: {params}")
    
    # Write parameters to output file
    output_file = write_parameters(input_file, params)
    logging.info(f"Parameters written to: {output_file}")
    
    # Print success message to stdout for the calling script
    print(f"Successfully wrote parameters to {output_file}")

if __name__ == "__main__":
    main()
