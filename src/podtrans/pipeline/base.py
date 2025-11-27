"""Base interfaces for pipeline stages.

All pipeline stages (ASR, Translation, TTS) should implement the PipelineStage
interface to ensure consistent behavior and easy integration.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

# Input and Output types for pipeline stages
InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType", bound=BaseModel)


class PipelineStage(ABC, Generic[InputType, OutputType]):
    """Base class for all pipeline stages.

    Each stage in the pipeline (ASR, Translation, TTS) should inherit from this
    class and implement the process() method.

    This provides a consistent interface for:
    - Processing data through the stage
    - Error handling
    - State management
    - Logging and metrics

    Example:
        class ASRStage(PipelineStage[Path, ASRResult]):
            def process(self, input_data: Path) -> ASRResult:
                # Perform ASR processing
                return asr_result
    """

    @abstractmethod
    def process(self, input_data: InputType) -> OutputType:
        """Process input data through this pipeline stage.

        Args:
            input_data: Input data for this stage. Type depends on the stage:
                - ASR: Path to audio file
                - Translation: ASRResult with segments to translate
                - TTS: TranslationResult with translated text

        Returns:
            Processed output data as a Pydantic model

        Raises:
            Exception: If processing fails
        """
        pass

    def validate_input(self, input_data: InputType) -> None:
        """Validate input data before processing.

        Override this method to add custom validation logic.

        Args:
            input_data: Input data to validate

        Raises:
            ValueError: If input is invalid
        """
        pass

    def cleanup(self) -> None:
        """Clean up resources after processing.

        Override this method to release resources (models, connections, etc.)
        """
        pass


class PipelineContext(BaseModel):
    """Context object passed through the pipeline.

    This contains metadata and intermediate results as data flows through
    the pipeline stages.
    """

    # Input metadata
    source_file: Path
    """Original audio file path"""

    # Stage outputs
    asr_result: Any | None = None
    """Output from ASR stage"""

    translation_result: Any | None = None
    """Output from Translation stage"""

    tts_result: Any | None = None
    """Output from TTS stage"""

    # Pipeline metadata
    pipeline_id: str | None = None
    """Unique identifier for this pipeline run"""

    metadata: dict[str, Any] = {}
    """Additional metadata (language, speakers, etc.)"""

    def get_stage_output(self, stage_name: str) -> Any:
        """Get output from a specific stage.

        Args:
            stage_name: Name of the stage (asr, translation, tts)

        Returns:
            Stage output or None if stage hasn't run yet
        """
        return getattr(self, f"{stage_name}_result", None)

    def set_stage_output(self, stage_name: str, output: Any) -> None:
        """Set output for a specific stage.

        Args:
            stage_name: Name of the stage (asr, translation, tts)
            output: Output data from the stage
        """
        setattr(self, f"{stage_name}_result", output)
