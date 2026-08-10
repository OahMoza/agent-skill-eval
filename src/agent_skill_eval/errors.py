"""Stable user-facing errors."""


class AgentSkillEvalError(Exception):
    """Base class for expected evaluation failures."""


class ConfigError(AgentSkillEvalError):
    """The evaluation configuration is invalid."""


class UnsupportedFeatureError(ConfigError):
    """The configuration requests a known feature outside this release."""


class AgentExecutionError(AgentSkillEvalError):
    """An agent process could not produce a usable result."""
