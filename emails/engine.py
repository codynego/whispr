from rules import RULE_REGISTRY, DefaultRule

class DynamicEmailProcessor:
    def __init__(self, user):
        self.user = user
        self.rules = self.load_user_rules()
        self.rules.append(DefaultRule())

    def load_user_rules(self):
        rules = []
        for r in self.user.email_rules.filter(is_active=True):
            rule_class = RULE_REGISTRY.get(f"{r.rule_type.capitalize()}Rule")
            if rule_class:
                if r.rule_type == "sender":
                    rules.append(rule_class([r.value]))
                elif r.rule_type == "keyword":
                    rules.append(rule_class(r.value.split(",")))
                else:
                    rules.append(rule_class())
        return rules

    def analyze_email(self, email):
        for rule in self.rules:
            if rule.apply(email):
                return rule.importance
        return "low"
