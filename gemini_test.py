import google.generativeai as genai

# 🔥 Put your API key here
genai.configure(api_key="AIzaSyB89ioI42jFrVfNYJjyivaB4Nf73WvNz8A")

try:
    model = genai.GenerativeModel("models/gemini-2.0-flash")
    response = model.generate_content("Write a short message if the API is working.")
    print("\n===== API RESPONSE =====\n")
    print(response.text)
    print("\n🎉 Success! The Gemini API is working.\n")

except Exception as e:
    print("\n❌ ERROR OCCURRED:\n")
    print(e)
