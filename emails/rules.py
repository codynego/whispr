# # rules.py

# # ────────────────────────────────────────────────
# #  Global Rule Registry
# # ────────────────────────────────────────────────
# RULE_REGISTRY = {}

# def register_rule(cls):
#     """Decorator to register rule classes automatically."""
#     RULE_REGISTRY[cls.__name__] = cls
#     return cls


# # ────────────────────────────────────────────────
# #  Base Class
# # ────────────────────────────────────────────────
# class EmailRule:
#     """Base class for all email rules."""
#     def __init__(self, name, importance="medium", score=1):
#         self.name = name
#         self.importance = importance
#         self.score = score

#     def apply(self, email):
#         """Return True if rule applies, False otherwise."""
#         raise NotImplementedError("Must implement apply method")


# # ────────────────────────────────────────────────
# #  Default & Built-in Rules
# # ────────────────────────────────────────────────

# @register_rule
# class SenderRule(EmailRule):
#     """Mark emails from specific senders as important."""
#     def __init__(self, sender_emails, importance="high", score=2):
#         super().__init__("SenderRule", importance, score)
#         self.sender_emails = [s.lower() for s in sender_emails]

#     def apply(self, email):
#         if not hasattr(email, "sender"):
#             return False
#         return email.sender.lower() in self.sender_emails


# @register_rule
# class KeywordRule(EmailRule):
#     """Mark emails containing certain keywords as important."""
#     def __init__(self, keywords, importance="medium", score=1):
#         super().__init__("KeywordRule", importance, score)
#         self.keywords = [k.lower().strip() for k in keywords]

#     def apply(self, email):
#         subject = (email.subject or "").lower()
#         body = (email.body or "").lower()
#         combined = f"{subject} {body}"
#         return any(keyword in combined for keyword in self.keywords)


# @register_rule
# class AttachmentRule(EmailRule):
#     """Marks emails with attachments as important."""
#     def __init__(self, importance="medium", score=2):
#         super().__init__("AttachmentRule", importance, score)

#     def apply(self, email):
#         return bool(getattr(email, "has_attachments", False))


# @register_rule
# class ReplyRule(EmailRule):
#     """Marks replies or threads as higher priority."""
#     def __init__(self, importance="high", score=2):
#         super().__init__("ReplyRule", importance, score)

#     def apply(self, email):
#         subject = getattr(email, "subject", "").lower()
#         return subject.startswith("re:") or subject.startswith("fw:")


# @register_rule
# class DefaultRule(EmailRule):
#     """Fallback rule for unclassified emails."""
#     def __init__(self, importance="medium", score=1):
#         super().__init__("DefaultRule", importance, score)

#     def apply(self, email):
#         return True  # Always applies as fallback


# # Optional AI placeholder (for future contextual rules)
# @register_rule
# class AIAssistedRule(EmailRule):
#     """Future placeholder for AI contextual tagging (Gemini/RAG)."""
#     def __init__(self, ai_model=None, importance="dynamic", score=3):
#         super().__init__("AIAssistedRule", importance, score)
#         self.ai_model = ai_model

#     def apply(self, email):
#         if not self.ai_model:
#             return False
#         return False  # Future logic
