
# Angle — using ai to make connections romantically

## References
hinge.com

## Overview
Angle is a dating app designed to help people build real relationships without endless swiping and texting. It uses AI-powered matchmaking to recommend compatible partners and limits messaging to encourage connecting.

**Target Audience:** College students looking for meaningful relationships.

## 1. Solves One Problem Extremely Well
Dating apps often encourage endless swiping and conversations that never lead to actual dates.

Angle focuses on helping users find compatible partners, exchange social handles safely, and move from online conversations to IRL interactions

## 2. Customer Access
Our primary customers are college students who use dating apps.

As college students ourselves, we have direct access to potential users through classmates, friends, and student organizations. We can conduct interviews, surveys, and user testing to collect feedback.

## 3. Technical Feasibility
We can build the application using technologies such as:

- **Frontend:** React and Tailwind CSS
- **Backend:** Django
- **Database:** PostgreSQL
- **AI:** LLM API for compatibility analysis (Gemini or OpenAI)
- **Matching Algorithm:** Python-based recommendation system

## 4. Reimagining the Existing Solution
Traditional dating apps rely heavily on swiping, profile appearances, and prolonged messaging.

Angle improves this experience through:

- AI-powered compatibility matching based on personality, values, and relationship goals.
- A limited number of curated matches instead of endless swiping.
- A shared character budget for conversations to encourage dates.
- A mutual "Share Handles" feature to exchange Instagram or Snapchat.

Rather than maximizing time spent on the app, Angle focuses on helping users build meaningful connections outside of it.

## 5. Essential Use of LLMs / Generative AI
LLMs are used for Angle's matchmaking system.

Users answer prompts about personalities, interests, lifestyles, and relationship expectations.

The LLM analyzes these responses and converts them into structured compatibility profiles.

The matching algorithm then uses these profiles to recommend compatible partners.

The LLM also generates personalized explanations of why two users may be compatible.

Unlike traditional matching algorithms that primarily compare predefined preferences, the LLM can interpret nuanced written responses to identify deeper similarities and differences.

## 6. LLM Output Validation
No LLM-generated profile or compatibility explanation will reach users without passing automated validation.

The system will verify:

- Outputs follow a predefined JSON schema.
- Generated attributes are supported by users' actual responses.
- Recommendations satisfy required preferences such as age range, distance, and relationship intentions.
- Compatibility explanations do not contain fabricated information.
- Generated content follows safety and formatting requirements.

If validation fails, the generated output will not be displayed.

## 7. Automatic Error Correction
When an LLM-generated output fails validation, the system will automatically send the validation errors back to the LLM.

The LLM will regenerate its response using the feedback.

The updated output will pass through the validator again before being accepted.

**Example workflow:**

1. User completes personality questionnaire.
2. LLM generates structured compatibility profile.
3. Validator checks accuracy, schema, and constraints.
4. If errors are detected, they are returned to the LLM.
5. LLM corrects its output.
6. Validator rechecks the corrected result.
7. Only validated outputs are stored or displayed.

If the output repeatedly fails validation, the system will stop retrying and request clarification instead of displaying unreliable information.

## 8. Deployment Feasibility
Angle can be developed and deployed as a functional web application.

Potential deployment infrastructure includes:

- **Frontend:** Vercel
- **Backend:** Render
- **Database:** Supabase PostgreSQL
- **AI:** Hosted LLM API

The initial MVP will include:

1. User registration and profiles.
2. AI-generated compatibility profiles.
3. Curated matchmaking recommendations.
4. Lightweight messaging with mutual social handle unlocks and campus date triggers.
5. Automated LLM validation and self-correction.

We will initially target a small community of college students to test the concept before considering expansion.

## Conclusion
Angle combines AI-powered matchmaking with intentional limits on messaging to address two common problems with dating apps: poor compatibility and conversations that never progress into real dates.

By prioritizing meaningful connections over engagement, Angle aims to create a dating experience that encourages users to spend less time on the app and more time connecting in person.
