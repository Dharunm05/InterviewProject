import random

def filter_questions(all_q, company, tech, difficulty, num_q):
    def match(q):
        if company and company not in q.get("company_tags", []):
            return False
        if tech and tech not in q.get("tech_tags", []):
            return False
        if difficulty and q.get("difficulty") != difficulty:
            return False
        return True

    filtered = [q for q in all_q if match(q)]
    random.shuffle(filtered)
    return filtered[:num_q]
