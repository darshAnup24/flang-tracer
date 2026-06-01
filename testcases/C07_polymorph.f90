! C07: Polymorphic CLASS dispatch
program polymorph_dispatch
    implicit none
    
    type :: Base
    contains
        procedure :: print_me => print_base
    end type
    
    type, extends(Base) :: Child
    contains
        procedure :: print_me => print_child
    end type
    
    class(Base), allocatable :: obj
    
    ! The construct below will be traced
    allocate(Child :: obj)
    call obj%print_me()

contains
    subroutine print_base(this)
        class(Base), intent(in) :: this
        print *, "Base"
    end subroutine

    subroutine print_child(this)
        class(Child), intent(in) :: this
        print *, "Child"
    end subroutine
end program polymorph_dispatch
