import json
import os
import re
from .base_agent import BaseAgent

try:
    import google.generativeai as genai
except ImportError:
    genai = None

class PersonaAgent(BaseAgent):
    """
    Generates human-readable customer personas from cluster profiles.
    
    Uses Gemini API to analyze cluster characteristics and create
    meaningful persona names and descriptions.
    """

    def __init__(self, api_key=None):
        """
        Initialize PersonaAgent.
        
        Args:
            api_key: Google API key (uses GOOGLE_API_KEY or GEMINI_API_KEY env var if not provided)
        """
        super().__init__("PersonaAgent")
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        
        if not self.api_key:
            self.log("Warning: GOOGLE_API_KEY not set. Personas will use fallback naming.")
        elif genai:
            genai.configure(api_key=self.api_key)
        else:
            self.log("Warning: google-generativeai package not installed. Using fallback.")

    def _generate_single_persona(self, cluster_info, features):
        """
        Generate a single persona using Gemini API.
        
        Args:
            cluster_info: Dict with cluster_id, size, characteristics
            features: List of feature names
            
        Returns:
            Dict with persona details
        """
        cluster_id = cluster_info["cluster_id"]
        size = cluster_info["size"]
        size_pct = cluster_info["size_percentage"]
        characteristics = cluster_info["characteristics"]

        # Format characteristics for LLM
        char_text = self._format_characteristics(characteristics)

        prompt = f"""Based on these customer segment characteristics, create a detailed persona name and description.

Segment Size: {size} customers ({size_pct:.1f}% of total)
Key Characteristics:
{char_text}

Create a JSON response with exactly this structure:
{{
  "cluster_id": {cluster_id},
  "persona_name": "A memorable, descriptive name (e.g., 'High-Value Frequent Shoppers')",
  "tagline": "A 1-2 sentence summary of this customer type",
  "description": "A 2-3 sentence detailed description of this persona",
  "key_traits": ["trait1", "trait2", "trait3"],
  "business_implications": "How should the business treat this segment?"
}}

Be specific and actionable. Use business terminology."""

        if self.api_key and genai:
            persona = self._call_gemini_api(prompt)
        else:
            persona = None
            
        if not persona:
            self.log(f"Using fallback persona naming for cluster {cluster_id}")
            persona = self._generate_fallback_persona(cluster_id, size_pct, characteristics)

        return persona

    def _call_gemini_api(self, prompt):
        """
        Call Gemini API to generate persona.
        
        Args:
            prompt: Prompt text for Gemini
            
        Returns:
            Dict with persona details or None if failed
        """
        try:
            # Using the fast, free tier capable 2.5 flash model
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # Utilizing JSON response type to guarantee structure
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                )
            )
            
            response_text = response.text
            
            # Since we enforce JSON mime type, it should parse directly
            persona = json.loads(response_text)
            return persona
                
        except Exception as e:
            self.log(f"Gemini API error: {e}. Using fallback.")
            return None

    def _generate_fallback_persona(self, cluster_id, size_pct, characteristics):
        """
        Generate persona using rule-based fallback when API unavailable.
        """
        # Analyze characteristics to generate persona name
        sorted_chars = sorted(
            characteristics, 
            key=lambda x: abs(x.get("mean", 0)), 
            reverse=True
        )
        
        top_features = [c["feature"] for c in sorted_chars[:3]]
        
        # Rule-based persona naming
        persona_name = self._infer_persona_name(top_features, size_pct)
        
        return {
            "cluster_id": cluster_id,
            "persona_name": persona_name,
            "tagline": f"A distinct segment representing {size_pct:.1f}% of customers",
            "description": f"Segment {cluster_id} is characterized by {', '.join(top_features[:2]) if top_features else 'various factors'}. "
                          f"This group represents {size_pct:.1f}% of the customer base.",
            "key_traits": top_features[:3],
            "business_implications": f"Tailor offerings to emphasize {top_features[0] if top_features else 'general engagement'} for maximum impact.",
        }

    def _infer_persona_name(self, top_features, size_pct):
        """
        Infer persona name from top features and segment size.
        """
        keyword_mapping = {
            "frequency": "Frequent",
            "visit": "Active",
            "purchase": "Buyer",
            "amount": "High-Value",
            "spend": "Big Spender",
            "engagement": "Engaged",
            "retention": "Loyal",
            "tenure": "Long-term",
            "recency": "Recent",
            "value": "Valuable",
            "ltv": "Valuable",
            "count": "Active",
            "avg": "Average",
        }

        persona_words = []
        for feature in top_features[:2]:
            feature_lower = feature.lower()
            for keyword, word in keyword_mapping.items():
                if keyword in feature_lower:
                    persona_words.append(word)
                    break

        if not persona_words:
            persona_words = ["Segment"]

        if size_pct > 30:
            size_desc = "Major"
        elif size_pct > 15:
            size_desc = "Significant"
        else:
            size_desc = "Niche"

        return f"{size_desc} {' '.join(persona_words)} Customers"

    def _format_characteristics(self, characteristics):
        """Format characteristics for readable prompt."""
        lines = []
        for char in characteristics:
            feature = char.get("feature", "unknown")
            mean = char.get("mean", 0)
            distribution = char.get("distribution", "normal")
            range_str = char.get("range", "N/A")
            lines.append(
                f"  • {feature}: avg={mean}, range={range_str}, distribution={distribution}"
            )
        return "\n".join(lines)

    def _create_persona_summary(self, personas):
        """Create a summary comparing all personas."""
        sorted_personas = sorted(personas, key=lambda p: p.get("cluster_id", 0))
        
        summary = {
            "total_personas": len(personas),
            "personas": sorted_personas,
            "comparison": self._compare_personas(sorted_personas),
        }
        
        return summary

    def _compare_personas(self, personas):
        """Generate comparative analysis of personas."""
        return {
            "distinct_segments": len(personas),
            "persona_names": [p["persona_name"] for p in personas],
            "key_differentiators": "See individual persona descriptions for nuanced differences",
        }
    
    def run(self, context):
        """
        Generate personas from segmentation results.
        """
        if "segmentation_result" not in context:
            raise ValueError("SegmentationAgent must run first to provide segmentation_result")

        segmentation = context["segmentation_result"]
        persona_input = segmentation["persona_input"]

        self.log(f"Generating personas for {len(persona_input['clusters'])} clusters...")

        personas = []
        for cluster_info in persona_input["clusters"]:
            persona = self._generate_single_persona(
                cluster_info, 
                segmentation["original_features"]
            )
            personas.append(persona)

        persona_summary = self._create_persona_summary(personas)

        context["personas"] = personas
        context["persona_summary"] = persona_summary

        self.log(f"Generated {len(personas)} personas successfully")
        return context