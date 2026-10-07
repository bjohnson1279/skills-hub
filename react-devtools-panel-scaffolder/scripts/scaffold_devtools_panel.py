import argparse
import os

def scaffold_panel(app_dir, panel_type, backends, css_framework):
    print(f"Analyzing component patterns in: {app_dir} (CSS Framework: {css_framework})")
    print(f"Targeting backends: {backends}")
    
    component_name = panel_type.title().replace('-', '') + "Panel"
    filename = f"{component_name}.tsx"
    filepath = os.path.join(app_dir, "components", "devtools", filename)
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Generate simple template based on panel_type
    content = f"""import React from 'react';

export const {component_name}: React.FC = () => {{
    return (
        <div className="glass-panel p-6 rounded-xl">
            <h2 className="text-2xl font-bold mb-4">{component_name}</h2>
            <p>Generated {panel_type} panel.</p>
            {{/* Implement your premium UI here */}}
        </div>
    );
}};
"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"\n✅ Successfully generated {component_name} at:")
    print(f"   {filepath}")
    
    print("\n📝 Integration Instructions:")
    print(f"1. Import the component in your main view:")
    print(f"   import {{ {component_name} }} from './components/devtools/{component_name}';")
    print(f"2. Add the panel to your Tab union type if applicable.")
    print(f"3. Add a sidebar navigation link for this panel.")
    print(f"4. Render the component when its tab is active.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scaffold React DevTools Panels")
    parser.add_argument("--app-dir", required=True, help="Path to React app src/ directory")
    parser.add_argument("--panel-type", required=True, choices=['health-monitor', 'conformance-viewer', 'spec-viewer', 'backend-switcher'], help="Type of panel to scaffold")
    parser.add_argument("--backends", required=True, help="Comma-separated backends (e.g., graphql:4000,express:5000)")
    parser.add_argument("--css-framework", required=True, choices=['vanilla', 'tailwind', 'modules'], help="CSS framework used in the app")
    
    args = parser.parse_args()
    
    scaffold_panel(args.app_dir, args.panel_type, args.backends.split(','), args.css_framework)
