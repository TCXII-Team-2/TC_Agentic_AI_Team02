import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from datetime import date

sys.path.append(str(Path(__file__).parent.parent))


from agents.agent_analyzer import QueryAnalyzer

class Ticket(BaseModel):
    content: str
    id: Optional[str] = None
    subject: str
    created_at: date
    userPlan: Optional[str] = None

async def test_single_ticket():
    """Test analyzing a single ticket"""
    print("🧪 Testing Query Analyzer - Single Ticket")
    print("=" * 50)
    
    analyzer = QueryAnalyzer()
    ticket1 = Ticket({
  "id": "TCK-001",
  "subject": "Unable to login to my account",
  "content": "I have been trying to login since yesterday but it keeps failing with an error message. Please help me regain access.",
  "created_at": date(2025, 2, 1),
  "userPlan": "Free"
})
    ticket2 = Ticket({
  "id": "TCK-002",
    "subject": "Payment issue - charged twice",
    "content": "I noticed that my credit card was charged twice for the same order. I need a refund for the duplicate charge as soon as possible.",
    "created_at": date(2025, 2, 2),
    "userPlan": "Premium"
})
    ticket3 = Ticket({
    "id": "TCK-003",
    "subject": "Comment mettre à jour mon profil ?",
    "content": "Je ne trouve pas l'option pour mettre à jour les informations de mon profil utilisateur. Pouvez-vous m'aider ?",
    "created_at": date(2025, 2, 3),
    "userPlan": "Standard"
})
    ticket4 = Ticket({  
    "id": "TCK-004",
    "subject": "الموقع لا يعمل على الهاتف",
    "content": "عند محاولة الدخول إلى الموقع من خلال الهاتف المحمول، يظهر لي خطأ ولا أستطيع الوصول إلى حسابي.",
    "created_at": date(2025, 2, 4),
    "userPlan": "Free"
})
    # Test tickets
    test_tickets = [
        ticket1,
        ticket2,
        ticket3,
        ticket4]
    
    for  ticket in test_tickets:
        print(f"Input: {ticket}...")
        
        try:
            result = await analyzer.analyze_query(ticket)
            
            if result:
                print(f"✅ Analysis successful!")
                print(f"   Category: {result['category']}")
                print(f"   Urgency: {result['urgency']}")
                print(f"   Language: {result['language']}")
                print(f"   Keywords: {', '.join(result['keywords'][:3])}")
                
                # Show full result
                print("\n📊 Full analysis:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                
                # Show report
                report = analyzer.get_analysis_report(result)
                print(report)
            else:
                print("❌ Analysis failed: Result is None")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    print("\n" + "=" * 50)

async def test_batch_tickets():
    """Test analyzing multiple tickets at once"""
    print("\n🧪 Testing Query Analyzer - Batch Mode")
    print("=" * 50)
    
    analyzer = QueryAnalyzer()
    
    ticket1 = Ticket(
  id= "TCK-001",
  subject= "Unable to login to my account",
  content= "I have been trying to login since yesterday but it keeps failing with an error message. Please help me regain access.",
  created_at= date(2025, 2, 1),
  userPlan= "Free"
)
    ticket2 = Ticket(
  id="TCK-002",
    subject= "Payment issue - charged twice",
    content= "I noticed that my credit card was charged twice for the same order. I need a refund for the duplicate charge as soon as possible.",
    created_at= date(2025, 2, 2),
    userPlan= "Premium"
)
    ticket3 = Ticket(
    id = "TCK-003",
    subject= "Comment mettre à jour mon profil ?",
    content= "Je ne trouve pas l'option pour mettre à jour les informations de mon profil utilisateur. Pouvez-vous m'aider ?",
    created_at= date(2025, 2, 3),
    userPlan= "Standard"
)
    ticket4 = Ticket(

    id = "TCK-004",
    subject= "الموقع لا يعمل على الهاتف",
    content= "عند محاولة الدخول إلى الموقع من خلال الهاتف المحمول، يظهر لي خطأ ولا أستطيع الوصول إلى حسابي.",
    created_at= date(2025, 2, 4),
    userPlan= "Free"
)
    # Test tickets
    tickets = [
        ticket1,
        ticket2,
        ticket3,
        ticket4]
    
    print(f"Processing {len(tickets)} tickets...")
    results = await analyzer.batch_analyze(tickets)
    
    for i, (ticket, result) in enumerate(zip(tickets, results), 1):
        print(f"\nTicket {i}: {ticket.content[:50]}...")
        if result:
            print(f"   ✅ {result} ")
        else:
            print("   ❌ Failed")

async def test_validation():
    """Test the validation logic"""
    print("\n🧪 Testing Validation Logic")
    print("=" * 50)
    
    analyzer = QueryAnalyzer()
    
    # Test with a valid analysis result
    valid_result = {
        "summary": "Test summary",
        "keywords": ["login", "error", "account"],
        "category": "Access",
        "urgency": "High",
        "language": "English",
        "sentiment": "Neutral",
    }
    
    try:
        is_valid = analyzer._validate_analysis(valid_result)
        print(f"✅ Valid result passes validation: {is_valid}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    # Test with invalid result (missing field)
    invalid_result = {
        "summary": "Test",
        "keywords": ["test"],
        "category": "InvalidCategory",  # Wrong category
        "urgency": "High",
        "language": "English",
        # Missing sentiment and requires_human
    }
    
    try:
        is_valid = analyzer._validate_analysis(invalid_result)
        print(f"✅ Invalid result correctly caught")
    except ValueError as e:
        print(f"❌ Correctly rejected: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

async def test_edge_cases():
    """Test edge cases"""
    print("\n🧪 Testing Edge Cases")
    print("=" * 50)
    
    analyzer = QueryAnalyzer()
    
    edge_cases = [
        "",  # Empty string
        "a",  # Very short
        "x" * 1000,  # Very long
        "1234567890",  # Numbers only
        "!@#$%^&*()",  # Symbols only
    ]
    
    for i, ticket in enumerate(edge_cases, 1):
        print(f"\nEdge case {i}: {ticket[:30]}...")
        try:
            result = await analyzer.analyze_query(ticket)
            if result:
                print(f"   Result: {result.get('category', 'Unknown')}")
            else:
                print("   Result: None (expected for edge cases)")
        except Exception as e:
            print(f"   Error: {type(e).__name__}")

def check_instructions_file():
    """Check if the instructions file exists"""
    print("\n📁 Checking Instructions File")
    print("=" * 50)
    
    instructions_path = Path("project/src/config/prompts/agent_analyzer.md")
    
    if instructions_path.exists():
        content = instructions_path.read_text(encoding="utf-8")
        print(f"✅ File exists: {instructions_path}")
        print(f"📄 First 200 chars: {content[:200]}...")
        return True
    else:
        print(f"❌ File not found: {instructions_path}")
        print("Make sure the path is correct:")
        print(f"Current working directory: {Path.cwd()}")
        print(f"Absolute path attempt: {instructions_path.absolute()}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Starting Query Analyzer Tests")
    print("=" * 50)
    
    # First check the instructions file
    if not check_instructions_file():
        print("\n⚠️  Cannot proceed without instructions file.")
        return
    
    # Run tests
    
    await test_batch_tickets()
    # await test_validation()
    # await test_edge_cases()
    
    print("\n" + "=" * 50)
    print("✅ All tests completed!")

if __name__ == "__main__":
    # Run the async tests
    asyncio.run(main())