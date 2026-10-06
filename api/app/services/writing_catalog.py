from dataclasses import dataclass

from app.ai.contracts import WritingField
from app.models.enums import WritingType


@dataclass(frozen=True, slots=True)
class WritingStepSpec:
    key: str
    question_fr: str
    required: bool = True
    hint_fr: str | None = None

    def as_field(self) -> WritingField:
        return WritingField(key=self.key, question_fr=self.question_fr, hint_fr=self.hint_fr)


@dataclass(frozen=True, slots=True)
class WritingTemplate:
    type: WritingType
    title_fr: str
    description_fr: str
    steps: tuple[WritingStepSpec, ...]

    def fields(self) -> tuple[WritingField, ...]:
        return tuple(step.as_field() for step in self.steps)


_FULL_NAME = WritingStepSpec("full_name", "Quel est ton prénom et ton nom ?")

WRITING_TEMPLATES: dict[WritingType, WritingTemplate] = {
    WritingType.CV_COVER_LETTER: WritingTemplate(
        type=WritingType.CV_COVER_LETTER,
        title_fr="CV et lettre de motivation",
        description_fr="Pour chercher un travail.",
        steps=(
            _FULL_NAME,
            WritingStepSpec(
                "contact",
                "Quel numéro de téléphone ou quelle adresse mettre pour te contacter ?",
            ),
            WritingStepSpec("target_job", "Quel travail tu cherches ?"),
            WritingStepSpec(
                "experience",
                "Raconte ton expérience de travail : où tu as travaillé, ce que tu faisais, "
                "et pendant combien de temps.",
                hint_fr="Garde chaque expérience avec son lieu, son rôle et sa durée.",
            ),
            WritingStepSpec("skills", "Qu'est-ce que tu sais bien faire ?"),
            WritingStepSpec(
                "education", "Quelles études ou formations tu as faites ?", required=False
            ),
            WritingStepSpec("languages", "Quelles langues tu parles ?", required=False),
        ),
    ),
    WritingType.REQUEST_LETTER: WritingTemplate(
        type=WritingType.REQUEST_LETTER,
        title_fr="Lettre de demande",
        description_fr="Pour une mairie, une école ou une administration.",
        steps=(
            _FULL_NAME,
            WritingStepSpec("address", "Quelle est ton adresse ?", required=False),
            WritingStepSpec("recipient", "À qui est destinée cette lettre ?"),
            WritingStepSpec("request", "Qu'est-ce que tu demandes ?"),
            WritingStepSpec("reason", "Pourquoi tu fais cette demande ?"),
        ),
    ),
    WritingType.BANK_LETTER: WritingTemplate(
        type=WritingType.BANK_LETTER,
        title_fr="Courrier à la banque",
        description_fr="Pour une demande ou une réclamation à ta banque.",
        steps=(
            _FULL_NAME,
            WritingStepSpec("bank_name", "Quelle est ta banque ?"),
            WritingStepSpec(
                "customer_reference",
                "Quel est ton numéro de client, si tu l'as ?",
                required=False,
            ),
            WritingStepSpec("request", "Qu'est-ce que tu demandes à la banque ?"),
            WritingStepSpec("reason", "Pourquoi tu fais cette demande ?"),
        ),
    ),
    WritingType.OTHER: WritingTemplate(
        type=WritingType.OTHER,
        title_fr="Autre courrier",
        description_fr="Pour tout autre courrier simple.",
        steps=(
            _FULL_NAME,
            WritingStepSpec("recipient", "À qui est destiné ce courrier ?"),
            WritingStepSpec("subject", "De quoi parle ce courrier ?"),
            WritingStepSpec("message", "Qu'est-ce que tu veux dire ?"),
        ),
    ),
}


def template_for(writing_type: WritingType) -> WritingTemplate:
    return WRITING_TEMPLATES[writing_type]
