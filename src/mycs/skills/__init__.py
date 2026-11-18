"""Optional answer skills. Add a folder with SKILL.md; the agent loop stays domain-free."""

from mycs.skills.loader import AnswerSkill, load_skills, match_skills

__all__ = ["AnswerSkill", "load_skills", "match_skills"]
