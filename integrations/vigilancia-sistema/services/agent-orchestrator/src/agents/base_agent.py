from abc import ABC, abstractmethod
from models import Incident, ActionProposal

class BaseAgent(ABC):
    """Contrato compartido por todos los agentes especializados.

    Cada agente implementa únicamente `assess`: recibe un incidente ya
    correlacionado y decide, dentro de su dominio de responsabilidad,
    si propone una acción. Un agente nunca ejecuta directamente: solo
    propone. La ejecución y el gate de validación humana viven en
    `human_validation.py` y `chain_communicator.py`.
    """

    name: str = "base"

    @abstractmethod
    def relevant(self, incident: Incident) -> bool:
        """True si este agente debe evaluar el incidente."""
        raise NotImplementedError

    @abstractmethod
    def assess(self, incident: Incident) -> ActionProposal | None:
        """Devuelve una propuesta de acción o None si no hay acción que tomar."""
        raise NotImplementedError
