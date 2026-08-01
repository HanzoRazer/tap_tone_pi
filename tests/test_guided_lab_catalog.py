"""Builder-goal catalog behaviour (DO-100).

Three things must hold: builder goals are the primary labels, only
``plate_measurement_setup`` resolves, and an unavailable goal fails explicitly
instead of returning a placeholder.
"""

from __future__ import annotations

import pytest

from tap_tone_pi.guided_lab import GuidedLabErrorCode, GuidedLabSessionError
from tap_tone_pi.guided_lab.catalog import (
    get_workflow_definition,
    list_workflow_intents,
)
from tap_tone_pi.guided_lab.validation import (
    require_unique_workflow_keys,
    validate_workflow_definition,
)
from tap_tone_pi.guided_lab.workflows import WORKFLOW_DEFINITIONS

ANALYZER_WORDS = (
    "fft",
    "spectrum",
    "analyzer",
    "analyser",
    "rayleigh",
    "ritz",
    "modal",
    "coherence",
    "transfer function",
    "ods",
)


class TestBuilderGoalsArePrimary:
    def test_every_title_is_written_in_the_first_person(self):
        for intent in list_workflow_intents():
            assert intent.title.lower().startswith("i want to"), intent.intent_id

    def test_no_title_leads_with_an_analyzer_name(self):
        for intent in list_workflow_intents():
            lowered = intent.title.lower()
            for word in ANALYZER_WORDS:
                assert not lowered.startswith(word), (intent.intent_id, word)

    def test_no_title_mentions_an_analyzer_at_all(self):
        for intent in list_workflow_intents():
            lowered = intent.title.lower()
            for word in ANALYZER_WORDS:
                assert word not in lowered, (intent.intent_id, word)

    def test_available_goal_is_listed_first(self):
        intents = list_workflow_intents()
        assert intents[0].available is True
        assert intents[0].workflow_id == "plate_measurement_setup"

    def test_intent_ids_are_unique(self):
        intents = list_workflow_intents()
        assert len({intent.intent_id for intent in intents}) == len(intents)

    def test_listing_is_a_stable_tuple(self):
        assert isinstance(list_workflow_intents(), tuple)
        assert list_workflow_intents() == list_workflow_intents()


class TestAvailability:
    def test_exactly_one_goal_is_available(self):
        available = [i for i in list_workflow_intents() if i.available]
        assert len(available) == 1

    def test_unavailable_goals_carry_a_reason(self):
        for intent in list_workflow_intents():
            if not intent.available:
                assert intent.unavailable_reason
                assert len(intent.unavailable_reason) > 20

    def test_unavailable_goals_are_still_listed(self):
        ids = {i.intent_id for i in list_workflow_intents()}
        assert {
            "compare_before_after",
            "investigate_wolf_note",
            "evaluate_plate_thickness",
        } <= ids

    def test_unavailable_goal_does_not_resolve(self):
        for intent in list_workflow_intents():
            if intent.available:
                continue
            with pytest.raises(GuidedLabSessionError) as excinfo:
                get_workflow_definition(intent.workflow_id)
            assert excinfo.value.code is GuidedLabErrorCode.WORKFLOW_NOT_AVAILABLE

    def test_unavailable_goal_is_not_reported_as_a_typo(self):
        """GDL-404 and GDL-402 answer different questions."""
        listed = next(i for i in list_workflow_intents() if not i.available)
        with pytest.raises(GuidedLabSessionError) as listed_error:
            get_workflow_definition(listed.workflow_id)
        with pytest.raises(GuidedLabSessionError) as unknown_error:
            get_workflow_definition("not_a_workflow")
        assert listed_error.value.code is not unknown_error.value.code

    def test_unavailable_goal_carries_the_reason_the_operator_was_shown(self):
        listed = next(i for i in list_workflow_intents() if not i.available)
        with pytest.raises(GuidedLabSessionError) as excinfo:
            get_workflow_definition(listed.workflow_id)
        context = excinfo.value.context
        assert context["intent_id"] == listed.intent_id
        assert context["unavailable_reason"] == listed.unavailable_reason

    def test_serialized_unavailable_intent_exposes_the_reason(self):
        intent = next(i for i in list_workflow_intents() if not i.available)
        payload = intent.to_dict()
        assert payload["available"] is False
        assert payload["unavailable_reason"]


class TestResolution:
    def test_plate_workflow_resolves(self):
        definition = get_workflow_definition("plate_measurement_setup")
        assert definition.workflow_id == "plate_measurement_setup"
        assert definition.workflow_version == 1

    def test_explicit_version_resolves(self):
        definition = get_workflow_definition("plate_measurement_setup", 1)
        assert definition.workflow_version == 1

    def test_unknown_version_is_gdl_402(self):
        with pytest.raises(GuidedLabSessionError) as excinfo:
            get_workflow_definition("plate_measurement_setup", 2)
        assert excinfo.value.code is GuidedLabErrorCode.UNKNOWN_WORKFLOW

    def test_unknown_workflow_is_gdl_402(self):
        with pytest.raises(GuidedLabSessionError) as excinfo:
            get_workflow_definition("not_a_workflow")
        assert excinfo.value.code is GuidedLabErrorCode.UNKNOWN_WORKFLOW

    def test_error_context_lists_what_is_available(self):
        with pytest.raises(GuidedLabSessionError) as excinfo:
            get_workflow_definition("not_a_workflow")
        assert excinfo.value.context["available_workflow_ids"] == [
            "plate_measurement_setup"
        ]

    def test_error_context_is_path_free(self):
        with pytest.raises(GuidedLabSessionError) as excinfo:
            get_workflow_definition("not_a_workflow")
        blob = repr(excinfo.value.to_dict())
        assert "C:" not in blob
        assert "\\\\" not in blob


class TestRegistryIntegrity:
    def test_every_available_intent_resolves(self):
        for intent in list_workflow_intents():
            if intent.available:
                assert get_workflow_definition(intent.workflow_id) is not None

    def test_every_shipped_definition_validates(self):
        for definition in WORKFLOW_DEFINITIONS:
            assert validate_workflow_definition(definition) == (), (
                definition.workflow_id
            )

    def test_shipped_registry_keys_are_unique(self):
        require_unique_workflow_keys(WORKFLOW_DEFINITIONS)

    def test_duplicate_registry_key_is_gdl_111(self):
        from tap_tone_pi.guided_lab import WorkflowDefinitionError

        doubled = WORKFLOW_DEFINITIONS + WORKFLOW_DEFINITIONS
        with pytest.raises(WorkflowDefinitionError) as excinfo:
            require_unique_workflow_keys(doubled)
        assert excinfo.value.code is GuidedLabErrorCode.DUPLICATE_WORKFLOW_KEY

    def test_duplicate_rejection_is_deterministic(self):
        from tap_tone_pi.guided_lab import WorkflowDefinitionError

        doubled = WORKFLOW_DEFINITIONS + WORKFLOW_DEFINITIONS
        contexts = []
        for _ in range(3):
            with pytest.raises(WorkflowDefinitionError) as excinfo:
                require_unique_workflow_keys(doubled)
            contexts.append(excinfo.value.to_dict())
        assert contexts[0] == contexts[1] == contexts[2]


class TestRegistryValidationTiming:
    """Authoring mistakes belong to the guided laboratory, not to `import`."""

    def test_importing_the_registry_does_not_validate_it(self):
        import tap_tone_pi.guided_lab.workflows as registry

        assert not hasattr(registry, "require_unique_workflow_keys")

    def test_the_catalog_checks_the_registry_on_first_use(self, monkeypatch):
        from tap_tone_pi.guided_lab import WorkflowDefinitionError, catalog

        monkeypatch.setattr(catalog, "_registry_checked", False)
        monkeypatch.setattr(
            catalog, "WORKFLOW_DEFINITIONS", WORKFLOW_DEFINITIONS + WORKFLOW_DEFINITIONS
        )
        with pytest.raises(WorkflowDefinitionError) as excinfo:
            catalog.shipped_workflow_definitions()
        assert excinfo.value.code is GuidedLabErrorCode.DUPLICATE_WORKFLOW_KEY

    def test_a_bad_registry_surfaces_through_resolution_too(self, monkeypatch):
        from tap_tone_pi.guided_lab import WorkflowDefinitionError, catalog

        monkeypatch.setattr(catalog, "_registry_checked", False)
        monkeypatch.setattr(
            catalog, "WORKFLOW_DEFINITIONS", WORKFLOW_DEFINITIONS + WORKFLOW_DEFINITIONS
        )
        with pytest.raises(WorkflowDefinitionError):
            catalog.get_workflow_definition("plate_measurement_setup")

    def test_the_shipped_registry_passes(self):
        from tap_tone_pi.guided_lab import catalog

        assert catalog.shipped_workflow_definitions() == WORKFLOW_DEFINITIONS


class TestShippedRegistryIsValidatedOnFirstUse:
    """Resolving a workflow must prove the registry sound, not merely unique.

    Only ``start_session`` validated a definition, so ``show`` and ``act`` would
    have gone on serving a definition the validator rejects. The check lives at
    the catalog now, which every command goes through.
    """

    def _reset_cache(self, monkeypatch, definitions):
        import tap_tone_pi.guided_lab.catalog as catalog_module

        monkeypatch.setattr(catalog_module, "_registry_checked", False)
        monkeypatch.setattr(catalog_module, "WORKFLOW_DEFINITIONS", definitions)
        return catalog_module

    def test_an_unsound_shipped_definition_is_refused(self, monkeypatch):
        import dataclasses

        from tap_tone_pi.guided_lab.errors import WorkflowDefinitionError

        broken = dataclasses.replace(
            WORKFLOW_DEFINITIONS[0], entry_node_id="no_such_node"
        )
        catalog_module = self._reset_cache(monkeypatch, (broken,))
        with pytest.raises(WorkflowDefinitionError):
            catalog_module.shipped_workflow_definitions()

    def test_a_sound_registry_still_resolves(self, monkeypatch):
        catalog_module = self._reset_cache(monkeypatch, WORKFLOW_DEFINITIONS)
        assert catalog_module.shipped_workflow_definitions() == WORKFLOW_DEFINITIONS

    def test_the_shipped_registry_passes_its_own_check(self):
        for definition in WORKFLOW_DEFINITIONS:
            assert validate_workflow_definition(definition) == ()
