import unittest

import run_weekly_pipeline as pipeline


class PipelineConfigTests(unittest.TestCase):
    def test_unvalidated_tiktok_is_not_a_default_source(self):
        self.assertNotIn("tiktok", pipeline.DEFAULT_SOURCES)
        self.assertIn("tiktok", pipeline.CONNECTORS)

    def test_action_agent_is_part_of_normal_workflow(self):
        self.assertTrue(pipeline.ACTION_AGENT.exists())
        self.assertTrue(pipeline.SNAPSHOT_BUILDER.exists())


if __name__ == "__main__":
    unittest.main()
