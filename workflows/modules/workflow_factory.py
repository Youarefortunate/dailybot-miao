from .workflow_manager import workflow_manager


class WorkflowFactory:
    """
    工作流工厂
    """

    @staticmethod
    def get_workflow(name: str):
        cls = workflow_manager.get_workflow_class(name)
        return cls() if cls else None

    @staticmethod
    def get_all_workflows():
        names = workflow_manager.get_all_workflow_names()
        workflows = []
        for name in names:
            wf = WorkflowFactory.get_workflow(name)
            if wf:
                workflows.append(wf)
        return workflows
