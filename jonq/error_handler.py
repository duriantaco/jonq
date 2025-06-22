# jonq/error_handler.py
import json
import re
from typing import Optional, Dict, Any, List

class JonqError(Exception):
    """Base exception for jonq errors with helpful messages"""
    
    def __init__(self, message: str, suggestion: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.suggestion = suggestion
        self.context = context or {}
    
    def format_error(self) -> str:
        """Format error with colors and suggestions"""
        RED = '\033[0;31m'
        YELLOW = '\033[1;33m'
        GREEN = '\033[0;32m'
        BLUE = '\033[0;34m'
        NC = '\033[0m' ### no color
        
        output = [f"{RED}Error: {self.args[0]}{NC}"]
        
        if self.context:
            output.append(f"\n{YELLOW}Context:{NC}")
            for key, value in self.context.items():
                output.append(f"  {key}: {value}")
        
        if self.suggestion:
            output.append(f"\n{GREEN}Suggestion: {self.suggestion}{NC}")
        
        return "\n".join(output)

class QuerySyntaxError(JonqError):
    """Raised when query syntax is invalid"""
    pass

class FieldNotFoundError(JonqError):
    """Raised when a field doesn't exist in the JSON"""
    pass

class AggregationError(JonqError):
    """Raised when aggregation fails"""
    pass

class ErrorAnalyzer:
    """Analyzes errors and provides helpful suggestions"""
    
    def __init__(self, json_file: str, query: str, jq_filter: str):
        self.json_file = json_file
        self.query = query
        self.jq_filter = jq_filter
        self.data = self._load_json_sample()
        
    def _load_json_sample(self) -> Any:
        """Load a sample of the JSON data for analysis"""
        try:
            with open(self.json_file, 'r') as f:
                sample = f.read(1024 * 1024)
                return json.loads(sample)
        except:
            return None
    
    def analyze_jq_error(self, stderr: str) -> JonqError:
        
        if "Cannot iterate over null" in stderr:
            return self._analyze_null_iteration_error(stderr)
        
        if "Cannot index array with string" in stderr:
            field = self._extract_field_from_error(stderr)
            return FieldNotFoundError(
                f"Trying to access field '{field}' on an array",
                suggestion=f"Use array index like [0].{field} or iterate with []",
                context={"query": self.query, "field": field}
            )
        
        if "is not defined" in stderr:
            return self._analyze_undefined_error(stderr)
        
        if "syntax error" in stderr:
            return QuerySyntaxError(
                "Invalid jq syntax generated",
                suggestion="This might be a bug in jonq. Please report it.",
                context={"query": self.query, "jq_filter": self.jq_filter}
            )
        
        return JonqError(
            stderr.strip(),
            context={"query": self.query, "jq_filter": self.jq_filter}
        )
    
    def _analyze_null_iteration_error(self, stderr: str) -> JonqError:
        """Analyze null iteration errors"""
        fields = re.findall(r'\.(\w+)', self.query)
        
        if self.data:
            null_fields = self._find_null_fields(self.data, fields)
            if null_fields:
                return FieldNotFoundError(
                    f"Field '{null_fields[0]}' is null or doesn't exist",
                    suggestion=f"Check if '{null_fields[0]}' exists in your JSON. Use 'select *' to see available fields.",
                    context={
                        "query": self.query,
                        "missing_field": null_fields[0],
                        "available_fields": self._get_available_fields(self.data)
                    }
                )
        
        return JonqError(
            "Cannot iterate over null values in your JSON",
            suggestion="Check if the field exists and contains data",
            context={"query": self.query}
        )
    
    def _analyze_undefined_error(self, stderr: str) -> JonqError:
        if any(func in stderr for func in ["avg/1", "max/1", "min/1", "sum/1"]):
            return AggregationError(
                "Aggregation function failed - field might not exist or contain non-numeric values",
                suggestion="Make sure the field exists and contains numbers",
                context={"query": self.query}
            )
        
        return JonqError(
            "Undefined function or operator",
            context={"query": self.query, "error": stderr}
        )
    
    def _find_null_fields(self, data: Any, fields: List[str]) -> List[str]:
        """Find which fields are null or missing"""
        null_fields = []
        
        if isinstance(data, list) and data:
            data = data[0] 
        
        for field in fields:
            parts = field.split('.')
            current = data
            field_exists = True
            
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    field_exists = False
                    break
            
            if not field_exists or current is None:
                null_fields.append(field)
        
        return null_fields

    def _get_available_fields(self, data: Any, prefix: str = "") -> List[str]:
        """Get list of available fields in the data"""
        fields = []
        
        if isinstance(data, list) and data:
            data = data[0]  
        
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key
                fields.append(full_key)
                
                if isinstance(value, dict) and len(full_key.split('.')) < 3:
                    fields.extend(self._get_available_fields(value, full_key))
        
        return fields
    
    def _extract_field_from_error(self, stderr: str) -> str:
        """Extract field name from error message"""
        match = re.search(r'"(\w+)"', stderr)
        return match.group(1) if match else "unknown"

def validate_query_against_schema(json_file: str, query: str) -> Optional[str]:
    """Pre-validate query against JSON schema"""
    try:
        with open(json_file, 'r') as f:
            sample = f.read(1024 * 1024)
            data = json.loads(sample)
        
        if any(x in query.lower() for x in ['count(', 'sum(', 'avg(', 'min(', 'max(', ' as ', '+', '-', '*', '/']):
            return None
            
        fields = re.findall(r'select\s+(.+?)(?:\s+if|\s+group|\s+sort|\s+from|$)', query, re.IGNORECASE)
        if not fields:
            return None
            
        field_list = [f.strip() for f in fields[0].split(',') if f.strip() not in ['*']]
        
        if isinstance(data, list) and data:
            data = data[0]
        
        if isinstance(data, dict):
            for field in field_list:
                if field == '*':
                    continue
                    
                parts = field.split('.')
                current = data
                for part in parts:
                    if not isinstance(current, dict) or part not in current:
                        return f"Field '{field}' not found. Available fields: {', '.join(data.keys())}"
                    current = current[part]
        
        return None
        
    except Exception:
        return None

def handle_error_with_context(error: Exception, json_file: str = None, 
                            query: str = None, jq_filter: str = None):
    
    if isinstance(error, JonqError):
        print(error.format_error())
    elif isinstance(error, RuntimeError) and "Error in jq filter:" in str(error):
        stderr = str(error).replace("Error in jq filter:", "").strip()
        analyzer = ErrorAnalyzer(json_file, query, jq_filter)
        jonq_error = analyzer.analyze_jq_error(stderr)
        print(jonq_error.format_error())
    else:
        print(f"Error: {error}")