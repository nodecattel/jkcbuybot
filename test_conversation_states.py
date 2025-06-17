#!/usr/bin/env python3
"""
Test script to verify conversation state constants are unique
"""

def test_conversation_states():
    """Test that all conversation state constants are unique"""
    print("🧪 Testing conversation state constants...")
    
    with open("telebot_fixed.py", 'r') as f:
        content = f.read()
    
    # Extract the constants section
    import re
    constants_match = re.search(r'# Constants for conversation handlers\n(.*?)\n\n', content, re.DOTALL)
    
    if constants_match:
        constants_section = constants_match.group(1)
        print("Found constants section:")
        print(constants_section)
        
        # Parse the constants
        constants = {}
        for line in constants_section.split('\n'):
            if '=' in line and not line.strip().startswith('#'):
                name, value = line.split('=', 1)
                name = name.strip()
                value = value.strip()
                constants[name] = value
        
        print(f"\n📊 Conversation State Constants:")
        values = []
        for name, value in constants.items():
            print(f"  {name} = {value}")
            values.append(int(value))
        
        # Check for duplicates
        if len(values) == len(set(values)):
            print("\n✅ All conversation state constants are unique!")
            return True
        else:
            duplicates = [v for v in values if values.count(v) > 1]
            print(f"\n❌ Found duplicate values: {set(duplicates)}")
            return False
    else:
        print("❌ Could not find constants section")
        return False

def test_handler_registration():
    """Test that conversation handlers are properly registered"""
    print("\n🧪 Testing conversation handler registration...")
    
    with open("telebot_fixed.py", 'r') as f:
        content = f.read()
    
    # Find all ConversationHandler registrations
    import re
    handlers = re.findall(r'application\.add_handler\(ConversationHandler\((.*?)\)\)', content, re.DOTALL)
    
    print(f"Found {len(handlers)} ConversationHandler registrations:")
    
    for i, handler in enumerate(handlers, 1):
        # Extract entry points
        entry_match = re.search(r'entry_points=\[(.*?)\]', handler)
        if entry_match:
            entry_points = entry_match.group(1)
            print(f"  {i}. Entry points: {entry_points}")
        
        # Extract states
        states_match = re.search(r'states=\{(.*?)\}', handler, re.DOTALL)
        if states_match:
            states = states_match.group(1)
            # Count the number of states
            state_count = len(re.findall(r'[A-Z_]+:', states))
            print(f"     States: {state_count} defined")
    
    return len(handlers) > 0

def main():
    """Run all tests"""
    print("🚀 Testing conversation handler setup...\n")
    
    test1_result = test_conversation_states()
    test2_result = test_handler_registration()
    
    print(f"\n🎯 Final Results:")
    print(f"  State Constants: {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"  Handler Registration: {'✅ PASS' if test2_result else '❌ FAIL'}")
    
    if test1_result and test2_result:
        print("\n🎉 Conversation handlers should work correctly now!")
        print("\n💡 The main issue was duplicate state constants:")
        print("  - INPUT_NUMBER and INPUT_IMAGE both had value 1")
        print("  - This caused conflicts in ConversationHandlers")
        print("  - Fixed by giving each state a unique value")
    else:
        print("\n⚠️  Some issues remain with conversation handlers.")

if __name__ == "__main__":
    main()
