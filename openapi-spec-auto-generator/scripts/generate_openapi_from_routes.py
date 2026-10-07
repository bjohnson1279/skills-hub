import argparse
import json
import os
import re
import yaml

def parse_express(content):
    routes = []
    # Simplified regex for demo
    mounts = re.findall(r"app\.use\(['\"]([^'\"]+)['\"],\s*(\w+)\)", content)
    for path in re.findall(r"app\.(get|post|put|delete)\(['\"]([^'\"]+)['\"]", content):
        routes.append({'method': path[0].lower(), 'path': path[1]})
    return routes

def parse_php(content):
    routes = []
    # Simplified regex for demo
    matches = re.findall(r"if\s*\(\$method\s*===\s*['\"](GET|POST|PUT|DELETE)['\"]\s*&&\s*\$path\s*===\s*['\"]([^'\"]+)['\"]\)", content)
    for match in matches:
        routes.append({'method': match[0].lower(), 'path': match[1]})
    return routes

def parse_ts_interfaces(content):
    schemas = {}
    interfaces = re.findall(r"interface\s+(\w+)\s*{([^}]+)}", content)
    for name, body in interfaces:
        props = {}
        for prop in re.findall(r"(\w+)(\??):\s*([\w\[\]]+)", body):
            prop_name = prop[0]
            is_optional = bool(prop[1])
            prop_type = prop[2]
            
            # Simple type mapping
            type_map = {'string': 'string', 'number': 'number', 'boolean': 'boolean'}
            json_type = type_map.get(prop_type.replace('[]', ''), 'object')
            
            if '[]' in prop_type:
                props[prop_name] = {'type': 'array', 'items': {'type': json_type}}
            else:
                props[prop_name] = {'type': json_type}
        
        schemas[name] = {
            'type': 'object',
            'properties': props
        }
    return schemas

def generate_openapi(routes, schemas, server_url, title):
    paths = {}
    for r in routes:
        path = r['path']
        method = r['method']
        if path not in paths:
            paths[path] = {}
        paths[path][method] = {
            'summary': f"{method.upper()} {path}",
            'operationId': f"{method}{path.replace('/', '_')}",
            'responses': {
                '200': {
                    'description': 'Success'
                }
            }
        }
        
    spec = {
        'openapi': '3.1.0',
        'info': {
            'title': title,
            'version': '1.0.0'
        },
        'servers': [{'url': server_url}],
        'paths': paths,
        'components': {
            'schemas': schemas,
            'securitySchemes': {
                'BearerAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'bearerFormat': 'JWT'
                }
            }
        },
        'security': [{'BearerAuth': []}]
    }
    return spec

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--express-entry', type=str)
    parser.add_argument('--php-entry', type=str)
    parser.add_argument('--types-file', type=str)
    parser.add_argument('--output-dir', type=str, required=True)
    parser.add_argument('--server-configs', type=str, required=True)
    args = parser.parse_args()
    
    server_configs = json.loads(args.server_configs)
    
    schemas = {}
    if args.types_file and os.path.exists(args.types_file):
        with open(args.types_file, 'r') as f:
            schemas = parse_ts_interfaces(f.read())
            
    routes = []
    if args.express_entry and os.path.exists(args.express_entry):
        with open(args.express_entry, 'r') as f:
            routes.extend(parse_express(f.read()))
            
    if args.php_entry and os.path.exists(args.php_entry):
        with open(args.php_entry, 'r') as f:
            routes.extend(parse_php(f.read()))
            
    os.makedirs(args.output_dir, exist_ok=True)
    
    for config in server_configs:
        name = config.get('name', 'api')
        url = config.get('url', 'http://localhost')
        
        spec = generate_openapi(routes, schemas, url, f"{name} API")
        
        out_path = os.path.join(args.output_dir, f"openapi-{name}.yaml")
        with open(out_path, 'w') as f:
            yaml.dump(spec, f, sort_keys=False)
        print(f"Generated {out_path} with {len(spec['paths'])} paths.")

if __name__ == '__main__':
    main()
