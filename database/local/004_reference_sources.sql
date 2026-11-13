-- Explicit additive migration for the local schema initially provisioned as v1.
-- Papers/catalogs are public references, never measured training examples.
ALTER TABLE study_sources DROP CONSTRAINT CONSTRAINT_1,
    ADD CONSTRAINT ck_study_source_origin CHECK (data_origin IN
        ('public_measured','public_synthetic','public_reference','ulisses_external'));
