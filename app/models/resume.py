from pydantic import BaseModel, ConfigDict


class ResumeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Link(ResumeModel):
    url: str
    display: str


class PersonalInfo(ResumeModel):
    name: str
    phone: str
    email: Link
    linkedin: Link
    github: Link


class Education(ResumeModel):
    institution: str
    location: str
    degree: str
    duration: str


class Skill(ResumeModel):
    title: str
    items: list[str]


class Project(ResumeModel):
    title: str
    tech_stack: str
    duration: str
    points: list[str]


class Resume(ResumeModel):
    personal_info: PersonalInfo
    objective: str
    education: list[Education]
    skills: list[Skill]
    projects: list[Project]
