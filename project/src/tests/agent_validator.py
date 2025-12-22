import asyncio
import sys
from pathlib import Path
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agents.agent_validator import TicketValidator, ValidationResult

async def test_single_validation():
    """Test validating a single ticket"""
    print("🧪 Testing TicketValidator - Single Ticket")
    print("=" * 60)
    
    # Initialize validator
    validator = TicketValidator()
    
    # Test cases with different scenarios
    test_cases = [
        {
            "name": "Complete Technical Ticket",
            "ticket": "I can't login to my admin account. Getting error 'Invalid credentials' when using correct password. Tried resetting password but same error. Using Chrome browser on Windows 11. Happening since yesterday at 3 PM.",
            "analysis": {
                "summary": "Login issue with error Invalid credentials",
                "keywords": ["login", "error", "credentials", "chrome", "windows"],
                "category": "Technical",
                "urgency": "High",
                "language": "English",
                "sentiment": "Frustrated",
                "requires_human": False
            }
        },
        {
            "name": "Incomplete Vague Ticket",
            "ticket": "The app is broken.",
            "analysis": {
                "summary": "App not working",
                "keywords": ["app", "broken", "not working"],
                "category": "Technical",
                "urgency": "Medium",
                "language": "English",
                "sentiment": "Neutral",
                "requires_human": False
            }
        },
        {
            "name": "Billing Issue",
            "ticket": "I was charged twice for my subscription. Invoice #INV-2024-00123 shows $49.99 charged on Jan 15th, but my bank shows two charges. Paid with Visa ending in 1234.",
            "analysis": {
                "summary": "Double charge for subscription",
                "keywords": ["double charge", "billing", "invoice", "subscription", "visa"],
                "category": "Billing",
                "urgency": "High",
                "language": "English",
                "sentiment": "Frustrated",
                "requires_human": False
            }
        },
        {
            "name": "Escalation Case",
            "ticket": "I want to speak to a manager NOW! My account was hacked and someone spent $1000!",
            "analysis": {
                "summary": "Account hacked with unauthorized charges",
                "keywords": ["hacked", "unauthorized", "charges", "manager", "security"],
                "category": "Billing",
                "urgency": "Critical",
                "language": "English",
                "sentiment": "Angry",
                "requires_human": True
            }
        },
        {
            "name": "French Ticket",
            "ticket": "Je ne peux pas accéder à mes fichiers. Le message d'erreur dit 'accès refusé'. Cela fait 2 jours.",
            "analysis": {
                "summary": "Cannot access files, error says access denied",
                "keywords": ["accès", "fichiers", "erreur", "refusé"],
                "category": "Access",
                "urgency": "Medium",
                "language": "French",
                "sentiment": "Frustrated",
                "requires_human": False
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n{'='*50}")
        print(f"Test: {test_case['name']}")
        print(f"Ticket: {test_case['ticket'][:80]}...")
        
        try:
            result = await validator.validate(
                ticket_text=test_case["ticket"],
                analysis_result=test_case["analysis"]
            )
            
            print(f"✅ Validation successful!")
            print(f"   Status: {result['validation_status']}")
            print(f"   Confidence: {result['confidence_score']:.0%}")
            print(f"   Is Valid: {result['is_valid']}")
            print(f"   Final Status: {result['final_status']}")
            
            if result['missing_details']:
                print(f"   Missing Details: {len(result['missing_details'])} items")
                for i, detail in enumerate(result['missing_details'][:3], 1):
                    print(f"     {i}. {detail}")
            
            if result['escalation_reason']:
                print(f"   Escalation Reason: {result['escalation_reason']}")
            
            if result['message_to_client']:
                print(f"\n   Message to Client:")
                print(f"   {result['message_to_client'][:100]}...")
            
            # Show JSON
            print(f"\n📊 Full Result:")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:500] + "...")
            
        except Exception as e:
            print(f"❌ Validation failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

async def test_batch_validation():
    """Test batch validation"""
    print("\n\n🧪 Testing Batch Validation")
    print("=" * 60)
    
    validator = TicketValidator()
    
    tickets = [
        ("Website is slow", {"category": "Technical", "urgency": "Medium"}),
        ("Need help with invoice", {"category": "Billing", "urgency": "Low"}),
        ("Can't reset password", {"category": "Access", "urgency": "High"}),
        ("How to export data?", {"category": "General", "urgency": "Low"})
    ]
    
    print(f"Processing {len(tickets)} tickets...")
    
    for i, (ticket_text, analysis) in enumerate(tickets, 1):
        print(f"\nTicket {i}: {ticket_text}")
        try:
            result = await validator.validate(ticket_text, analysis)
            print(f"   → {result['validation_status']} (Confidence: {result['confidence_score']:.0%})")
        except Exception as e:
            print(f"   → ❌ Failed: {e}")

async def test_validation_rules():
    """Test that validation rules are loaded correctly"""
    print("\n\n🧪 Testing Validation Rules")
    print("=" * 60)
    
    validator = TicketValidator()
    
    print("Validation Rules by Category:")
    rules = validator._get_validation_rules()
    
    for category, requirements in rules.items():
        print(f"\n{category}:")
        for req in requirements:
            print(f"  - {req}")
    
    print(f"\nTotal categories: {len(rules)}")
    print(f"Total rules: {sum(len(reqs) for reqs in rules.values())}")

async def test_edge_cases():
    """Test edge cases"""
    print("\n\n🧪 Testing Edge Cases")
    print("=" * 60)
    
    validator = TicketValidator()
    
    edge_cases = [
        ("", {}),  # Empty ticket
        ("a", {}),  # Very short
        ("x" * 500, {}),  # Very long
    ]
    
    for i, (ticket_text, analysis) in enumerate(edge_cases, 1):
        print(f"\nEdge Case {i}: '{ticket_text[:50]}...'")
        try:
            result = await validator.validate(ticket_text, analysis)
            print(f"   → Status: {result['validation_status']}")
        except Exception as e:
            print(f"   → ❌ Error: {type(e).__name__}: {e}")

async def test_result_validation():
    """Test the _validate_result method"""
    print("\n\n🧪 Testing Result Validation")
    print("=" * 60)
    
    validator = TicketValidator()
    
    # Test valid result
    valid_result = {
        "is_valid": True,
        "validation_status": ValidationResult.VALID,
        "missing_details": [],
        "escalation_reason": None,
        "message_to_client": None,
        "confidence_score": 0.95
    }
    
    try:
        is_valid = validator._validate_result(valid_result)
        print(f"✅ Valid result passes: {is_valid}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    # Test invalid results
    invalid_cases = [
        {
            "name": "Missing field",
            "data": {
                "is_valid": True,
                # Missing validation_status
                "missing_details": [],
                "escalation_reason": None,
                "message_to_client": None,
                "confidence_score": 0.5
            }
        },
        {
            "name": "Wrong type",
            "data": {
                "is_valid": "true",  # Should be bool
                "validation_status": ValidationResult.VALID,
                "missing_details": [],
                "escalation_reason": None,
                "message_to_client": None,
                "confidence_score": 0.5
            }
        },
        {
            "name": "Invalid status",
            "data": {
                "is_valid": True,
                "validation_status": "wrong_status",
                "missing_details": [],
                "escalation_reason": None,
                "message_to_client": None,
                "confidence_score": 0.5
            }
        },
        {
            "name": "Invalid confidence",
            "data": {
                "is_valid": True,
                "validation_status": ValidationResult.VALID,
                "missing_details": [],
                "escalation_reason": None,
                "message_to_client": None,
                "confidence_score": 1.5  # > 1
            }
        }
    ]
    
    for case in invalid_cases:
        print(f"\nTesting {case['name']}:")
        try:
            validator._validate_result(case['data'])
            print(f"❌ Should have failed but didn't")
        except ValueError as e:
            print(f"✅ Correctly rejected: {str(e)[:80]}...")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

def check_instructions_file():
    """Check if instructions file exists"""
    print("\n📁 Checking Instructions File")
    print("=" * 60)
    
    instructions_path = Path("project/src/config/prompts/agent_validator.md")
    
    if instructions_path.exists():
        content = instructions_path.read_text(encoding="utf-8")
        print(f"✅ File exists: {instructions_path}")
        print(f"📄 First 200 chars:\n{content[:200]}...")
        return True
    else:
        print(f"❌ File not found: {instructions_path}")
        
        # Try other paths
        alternative_paths = [
            Path("project/src/config/prompts/agent_validator.md"),
            Path("../config/prompts/agent_validator.md"),
            Path(__file__).parent / "config/prompts/agent_validator.md"
        ]
        
        for path in alternative_paths:
            if path.exists():
                print(f"✅ Found at alternative path: {path}")
                return True
        
        print("\n⚠️  Create the instructions file with this content:")
        print("""
        You are a ticket validation expert. Check if tickets have enough details.
        
        Output JSON with: is_valid, validation_status, missing_details, 
        escalation_reason, message_to_client, confidence_score
        """)
        return False

async def main():
    """Run all tests"""
    print("🚀 Starting TicketValidator Tests")
    print("=" * 60)
    
    # Check instructions file
    if not check_instructions_file():
        print("\n⚠️  Cannot proceed without instructions file.")
        return
    
    try:
        # Run tests
        await test_single_validation()
        await test_batch_validation()
        await test_validation_rules()
        await test_edge_cases()
        await test_result_validation()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run async tests
    asyncio.run(main())