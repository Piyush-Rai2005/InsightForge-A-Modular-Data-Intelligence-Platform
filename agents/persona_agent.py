import json
import os
from .base_agent import BaseAgent


class PersonaAgent(BaseAgent):
    """
    Generates human-readable customer personas from cluster profiles.
    
    Uses Claude API to analyze cluster characteristics and create
    meaningful persona names and descriptions.
    """

    def __init__(self, api_key=None):
        """
        Initialize PersonaAgent.
        
        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        """
        super().__init__("PersonaAgent")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            self.log("Warning: ANTHROPIC_API_KEY not set. Personas will use fallback naming.")

    def _generate_single_persona(self, cluster_info, features):
        """
        Generate a single persona using Claude API.
        
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

        if self.api_key:
            persona = self._call_claude_api(prompt)
        else:
            self.log(f"Using fallback persona naming for cluster {cluster_id}")
            persona = self._generate_fallback_persona(cluster_id, size_pct, characteristics)

        return persona

    def _call_claude_api(self, prompt):
        """
        Call Claude API to generate persona.
        
        Args:
            prompt: Prompt text for Claude
            
        Returns:
            Dict with persona details
        """
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.api_key)
            
            message = client.messages.create(
                model="claude-opus-4-20250805",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = message.content[0].text
            
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                persona = json.loads(json_match.group())
                return persona
            else:
                self.log("Could not parse JSON from Claude response, using fallback")
                return None
                
        except Exception as e:
            self.log(f"Claude API error: {e}. Using fallback.")
            return None

    def _generate_fallback_persona(self, cluster_id, size_pct, characteristics):
        """
        Generate persona using rule-based fallback when API unavailable.
        
        Args:
            cluster_id: Cluster identifier
            size_pct: Percentage of total
            characteristics: List of feature summaries
            
        Returns:
            Dict with persona details
        """
        # Analyze characteristics to generate persona name
        sorted_chars = sorted(
            characteristics, 
            key=lambda x: abs(x["mean"]), 
            reverse=True
        )
        
        top_features = [c["feature"] for c in sorted_chars[:3]]
        
        # Rule-based persona naming
        persona_name = self._infer_persona_name(top_features, size_pct)
        
        return {
            "cluster_id": cluster_id,
            "persona_name": persona_name,
            "tagline": f"A distinct segment representing {size_pct:.1f}% of customers",
            "description": f"Segment {cluster_id} is characterized by {', '.join(top_features[:2])}. "
                          f"This group represents {size_pct:.1f}% of the customer base.",
            "key_traits": top_features[:3],
            "business_implications": f"Tailor offerings to emphasize {top_features[0]} for maximum impact.",
        }

    def _infer_persona_name(self, top_features, size_pct):
        """
        Infer persona name from top features and segment size.
        
        Args:
            top_features: List of top feature names
            size_pct: Segment size as percentage
            
        Returns:
            str: Inferred persona name
        """
        # Common feature keywords for persona generation
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

        # Add size indicator
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
            feature = char["feature"]
            mean = char["mean"]
            distribution = char["distribution"]
            range_str = char["range"]
            lines.append(
                f"  • {feature}: avg={mean}, range={range_str}, distribution={distribution}"
            )
        return "\n".join(lines)

    def _create_persona_summary(self, personas):
        """
        Create a summary comparing all personas.
        
        Args:
            personas: List of persona dicts
            
        Returns:
            Dict with comparative summary
        """
        sorted_personas = sorted(personas, key=lambda p: p.get("cluster_id", 0))
        
        summary = {
            "total_personas": len(personas),
            "personas": sorted_personas,
            "comparison": self._compare_personas(sorted_personas),
        }
        
        return summary

    def _compare_personas(self, personas):
        """
        Generate comparative analysis of personas.
        
        Args:
            personas: List of persona dicts
            
        Returns:
            Dict with comparison insights
        """
        return {
            "distinct_segments": len(personas),
            "persona_names": [p["persona_name"] for p in personas],
            "key_differentiators": "See individual persona descriptions for nuanced differences",
        }
    
    def run(self, context):
        """
        Generate personas from segmentation results.
        
        Args:
            context: Dict with segmentation_result from SegmentationAgent
            
        Returns:
            context: Updated with persona_descriptions
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