import enum


class PhaseKind(str, enum.Enum):
    TUTORIAL = "tutorial"
    EXPLORATION = "exploration"
    COMBAT = "combat"
    BOSS = "boss"
    PUZZLE = "puzzle"
    MENU = "menu"
    CUTSCENE = "cutscene"
    DIALOGUE = "dialogue"
    LOADING = "loading"
    IDLE = "idle"
    OTHER = "other"


class FrictionSource(str, enum.Enum):
    DIFFICULTY_SPIKE = "difficulty_spike"
    UNCLEAR_OBJECTIVE = "unclear_objective"
    CONTROLS = "controls"
    CAMERA = "camera"
    BUG = "bug"
    REPETITION = "repetition"
    UNFAIR_MECHANIC = "unfair_mechanic"
    UI_CONFUSION = "ui_confusion"
    OTHER = "other"


class FrictionSeverity(str, enum.Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    SEVERE = "severe"


class StopRisk(str, enum.Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClarityIssueType(str, enum.Enum):
    UNCLEAR_OBJECTIVE = "unclear_objective"
    TUTORIAL_GAP = "tutorial_gap"
    MISLEADING_AFFORDANCE = "misleading_affordance"
    CONFUSING_UI = "confusing_ui"
    POOR_FEEDBACK = "poor_feedback"
    MISSING_SIGNPOST = "missing_signpost"
    OTHER = "other"


class ClaritySeverity(str, enum.Enum):
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class DelightDriver(str, enum.Enum):
    COMBAT = "combat"
    STORY = "story"
    EXPLORATION = "exploration"
    VISUAL_DESIGN = "visual_design"
    MASTERY = "mastery"
    PROGRESSION = "progression"
    DISCOVERY = "discovery"
    HUMOR = "humor"
    OTHER = "other"


class DelightStrength(str, enum.Enum):
    LIGHT = "light"
    CLEAR = "clear"
    STRONG = "strong"
    SIGNATURE = "signature"


class BugCategory(str, enum.Enum):
    GRAPHICS = "graphics"
    ANIMATION = "animation"
    PHYSICS = "physics"
    AUDIO = "audio"
    PERFORMANCE = "performance"
    UI_RENDERING = "ui_rendering"
    GAMEPLAY_LOGIC = "gameplay_logic"
    COLLISION = "collision"
    OTHER = "other"


class BugSeverity(str, enum.Enum):
    COSMETIC = "cosmetic"
    PLAY_AFFECTING = "play_affecting"
    BLOCKING = "blocking"


class AgentKind(str, enum.Enum):
    TIMELINE = "timeline"
    FRICTION = "friction"
    CLARITY = "clarity"
    DELIGHT = "delight"
    QUALITY = "quality"
    SENTIMENT = "sentiment"
    RETRY = "retry"
    VERBAL = "verbal"


class VideoSourceType(str, enum.Enum):
    LOCAL = "local"
    YOUTUBE = "youtube"


class EmotionLabel(str, enum.Enum):
    FRUSTRATED = "frustrated"
    CONFUSED = "confused"
    BORED = "bored"
    NEUTRAL = "neutral"
    FOCUSED = "focused"
    AMUSED = "amused"
    EXCITED = "excited"
    TRIUMPHANT = "triumphant"


class SilenceType(str, enum.Enum):
    FOCUSED = "focused"
    RESIGNED = "resigned"
    CONFUSED = "confused"
    TENSE = "tense"
    IDLE = "idle"


class VerbalCategory(str, enum.Enum):
    COMPLAINT = "complaint"
    PRAISE = "praise"
    QUESTION = "question"
    NARRATION = "narration"
    STRATEGY = "strategy"
    SUGGESTION = "suggestion"
    REACTION = "reaction"


class RetryOutcome(str, enum.Enum):
    SUCCEEDED = "succeeded"
    ABANDONED = "abandoned"
    STILL_TRYING = "still_trying"


class InsightConfidence(str, enum.Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    SUGGESTIVE = "suggestive"


__all__ = [
    "AgentKind",
    "BugCategory",
    "BugSeverity",
    "ClarityIssueType",
    "ClaritySeverity",
    "DelightDriver",
    "DelightStrength",
    "EmotionLabel",
    "FrictionSeverity",
    "FrictionSource",
    "InsightConfidence",
    "PhaseKind",
    "RetryOutcome",
    "SilenceType",
    "StopRisk",
    "VerbalCategory",
    "VideoSourceType",
]
